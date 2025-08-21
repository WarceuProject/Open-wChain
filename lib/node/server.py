# lib/node/server.py
import os
import sys
import requests
import logging
import time
import json
import threading
from flask import Flask, request, jsonify
from app.config import FEE_RATE

# make project root importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lib.chain.blockchain import (
    mine_block, save_chain, load_chain, is_block_valid, update_wallets_from_chain, hash_block, 
)
from lib.chain.tx_pool import add_transaction, load_tx_pool, save_tx_pool
from lib.node.peers import load_peers, add_peer, save_peers
from lib.wallet.wallet import verify_signature, load_wallets, save_wallets

# ======================= Logging =======================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("wcn-node")

# ======================= Flask App =======================
app = Flask(__name__)

# ======================= Configurable =======================
SYNC_INTERVAL = int(os.getenv("WCN_SYNC_INTERVAL", "10"))  # seconds
RPC_TIMEOUT = int(os.getenv("WCN_RPC_TIMEOUT", "3"))
NODE_PORT = int(os.getenv("WCN_NODE_PORT", "8000"))
SELF_URL = os.getenv("NODE_URL", None)

def get_self_url():
    if SELF_URL:
        return SELF_URL.rstrip('/')
    host = os.getenv("HOSTNAME", "localhost")
    return f"http://{host}:{NODE_PORT}"

def node_url_from_addr(addr):
    if not addr:
        return None
    addr = str(addr).strip()
    if addr.startswith("http://") or addr.startswith("https://"):
        return addr.rstrip('/')
    if addr.startswith("//"):
        addr = addr.lstrip('/')
    if ":" in addr:
        return f"http://{addr}".rstrip('/')
    return f"http://{addr}:{NODE_PORT}".rstrip('/')

def validate_chain_structure(chain):
    try:
        wallets_master = load_wallets()
        address_map = {w['address']: {'balance': w.get('balance', 0)} for w in wallets_master}
        for i, block in enumerate(chain):
            computed = hash_block(block)
            if block.get('hash') != computed:
                log.warning(f"[VALIDATE] Block {i} hash mismatch")
                return False
            if i > 0 and block.get('previous_hash') != chain[i-1].get('hash'):
                log.warning(f"[VALIDATE] Block {i} previous_hash mismatch")
                return False
            if not block.get('hash', '').startswith('0000'):
                log.warning(f"[VALIDATE] Block {i} doesn't meet difficulty prefix")
                return False
            for tx in block.get('transactions', []):
                if tx.get('from') == 'COINBASE':
                    to_addr = tx.get('to')
                    amount = tx.get('value', 0)
                    address_map.setdefault(to_addr, {'balance': 0})
                    address_map[to_addr]['balance'] += amount
                    continue
                txdata = tx.get('data')
                sig = tx.get('signature')
                pub = tx.get('publicKey') or tx.get('public_key') or None
                if not txdata or not sig or not pub:
                    log.warning(f"[VALIDATE] Missing signature/pub/txdata in tx in block {i}")
                    return False
                if not verify_signature(txdata, tx['signature'], pub):
                    log.warning(f"[VALIDATE] Bad signature in block {i}")
                    return False
                sender = tx.get('from')
                value = txdata.get('value', 0)
                to_addr = txdata.get('to')
                address_map.setdefault(sender, {'balance': 0})
                if address_map[sender]['balance'] < value:
                    log.warning(f"[VALIDATE] Insufficient balance for {sender}")
                    return False
                address_map[sender]['balance'] -= value
                address_map.setdefault(to_addr, {'balance': 0})
                address_map[to_addr]['balance'] += value
        return True
    except Exception as e:
        log.exception(f"[VALIDATE] Exception validating chain: {e}")
        return False

# ======================= Auto-sync =======================
last_known_height = 0
last_sync_time = 0
MIN_SYNC_INTERVAL = 300

def get_local_height():
    return len(load_chain())

def get_peer_height(peer_url):
    try:
        res = requests.post(f"{peer_url}/rpc", json={"method": "wcn_blockNumber"}, timeout=RPC_TIMEOUT)
        if res.status_code == 200:
            result = res.json().get("result")
            if isinstance(result, str) and result.startswith("0x"):
                return int(result, 16)
            return int(result)
    except Exception:
        return None
    return None
def auto_sync_from_peers():
    """
    Fetch full chain from peers and replace local chain if a longer valid chain is found.
    Returns True if local chain was replaced, else False.
    """
    peers = load_peers()
    if not peers:
        return False
    local_chain = load_chain()
    local_len = len(local_chain)
    replaced = False
    for p in peers:
        peer_url = node_url_from_addr(p)
        try:
            res = requests.get(f"{peer_url}/fullchain", timeout=RPC_TIMEOUT)
            if res.status_code != 200:
                continue
            data = res.json()
            peer_chain = data.get('chain', [])
            peer_len = int(data.get('length', len(peer_chain)))
            if peer_len > local_len and validate_chain_structure(peer_chain):
                save_chain(peer_chain)
                update_wallets_from_chain(peer_chain)
                log.info(f"[SYNC] Local chain replaced from peer {peer_url} (len {peer_len})")
                replaced = True
                break
        except Exception as e:
            log.debug(f"[SYNC] Failed fetching chain from {peer_url}: {e}")
    return replaced

def auto_sync_from_peers_if_needed():
    global last_known_height, last_sync_time
    now = time.time()
    local_height = get_local_height()
    if now - last_sync_time < MIN_SYNC_INTERVAL:
        return False
    peers = load_peers()
    if not peers:
        log.debug("[SYNC] No peers to check height.")
        return False
    should_sync = False
    for p in peers:
        h = get_peer_height(node_url_from_addr(p))
        if h is not None and h > local_height:
            log.info(f"[SYNC] Peer {p} has newer height {h} > {local_height}")
            should_sync = True
            break
    if should_sync:
        replaced = auto_sync_from_peers()
        if replaced:
            last_known_height = get_local_height()
            last_sync_time = time.time()
        return replaced
    else:
        log.debug("[SYNC] No newer blocks found in peers.")
        last_sync_time = now
    return False

def background_sync_worker():
    while True:
        try:
            auto_sync_from_peers_if_needed()
        except Exception:
            log.exception("[SYNC] background_sync_worker exception")
        time.sleep(SYNC_INTERVAL)

def start_background_sync():
    t = threading.Thread(target=background_sync_worker, daemon=True)
    t.start()

# ======================= Bootstrap =======================
def bootstrap_peers():
    peers = load_peers()
    if not peers:
        log.info("[BOOT] No peers configured to bootstrap.")
        return
    self_url = get_self_url()
    log.info(f"[BOOT] Starting bootstrap. self_url={self_url} peers_count={len(peers)}")
    normalized = []
    for p in peers:
        u = node_url_from_addr(p)
        if u:
            normalized.append(u)
    if normalized:
        save_peers(normalized)
    for peer_url in normalized:
        try:
            try:
                requests.post(f"{peer_url}/add_peer", json={"url": self_url}, timeout=RPC_TIMEOUT)
                log.info(f"[BOOT] Announced self to {peer_url}")
            except Exception:
                log.debug(f"[BOOT] Announce failed to {peer_url} (non-fatal)")
            try:
                res = requests.get(f"{peer_url}/fullchain", timeout=RPC_TIMEOUT)
                if res.status_code == 200:
                    data = res.json()
                    new_chain = data.get('chain', [])
                    new_len = int(data.get('length', len(new_chain)))
                    local_len = len(load_chain())
                    if new_len > local_len and validate_chain_structure(new_chain):
                        save_chain(new_chain)
                        update_wallets_from_chain(new_chain)
                        log.info(f"[BOOT] Replaced local chain from peer {peer_url} len={new_len}")
            except Exception as e:
                log.debug(f"[BOOT] Failed fetching chain from {peer_url}: {e}")
        except Exception as e:
            log.debug(f"[BOOT] unexpected error with peer {peer_url}: {e}")

# ======================= Transaction fee =======================
def calculate_fee(tx):
    tx_size = len(json.dumps(tx).encode("utf-8"))
    return tx_size * FEE_RATE

# ======================= Flask Endpoints =======================
@app.route("/")
def home():
    return {"status": "running"}

@app.route('/fullchain', methods=['GET'])
def full_chain():
    chain = load_chain()
    return jsonify({'length': len(chain), 'chain': chain})

@app.route('/rpc', methods=['POST'])
def rpc():
    data = request.json or {}
    method = data.get('method')
    params = data.get('params', [])
    log.info(f"[RPC] {method} params={params}")

    if method == 'wcn_blockNumber':
        return jsonify({'result': hex(len(load_chain()))})

    elif method == 'wcn_mineBlock':
        miners = params if isinstance(params, list) else [params[0]] if params else []
        if not miners:
            return jsonify({'error': 'No miner address provided'}), 400
        block = mine_block(miners, [])
        reward_total = sum(tx.get('value', 0) for tx in block.get('transactions', []) if tx.get('from') == 'COINBASE')
        log.info(f"[MINE] Mined block idx={block.get('index')} hash={block.get('hash')} reward={reward_total}")
        for p in load_peers():
            try:
                requests.post(f"{node_url_from_addr(p)}/sync", json=block, timeout=RPC_TIMEOUT)
            except Exception:
                continue
        return jsonify({'result': block, 'reward': reward_total})

    elif method == 'wcn_getBalance':
        address = params[0] if params else None
        if not address:
            return jsonify({'error': 'No address provided'}), 400
        balance = calculate_balance(address)
        return jsonify({'result': balance})

    elif method == 'wcn_sendTransaction':
        tx = params[0] if params else None
        if not tx:
            return jsonify({'error': 'No transaction provided'}), 400
        public_key = tx.get("publicKey")
        sender = tx.get("from")
        to = (tx.get("data") or {}).get("to")
        value = (tx.get("data") or {}).get("value")
        log.info(f"[TX] Received tx from {sender} -> {to} value={value}")
        MIN_TRANSFER = 100_000
        if value is None or value < MIN_TRANSFER:
            return jsonify({'error': f'Transfer too small. Minimum is {MIN_TRANSFER}'}), 400
        fee = calculate_fee(tx)
        tx['fee'] = fee
        if not public_key or not verify_signature(tx['data'], tx['signature'], public_key):
            log.warning("[TX] Invalid signature")
            return jsonify({'error': 'Invalid signature'}), 400
        balance = calculate_balance(sender)
        if balance < (value + fee):
            log.warning(f"[TX] Insufficient balance for {sender}")
            return jsonify({'error': 'Insufficient balance including fee', 'available': balance}), 400
        add_transaction(tx)
        log.info(f"[TX] Transaction accepted {sender} -> {to} fee={fee}")
        return jsonify({'result': 'Transaction added to pool', 'fee': fee})

    else:
        return jsonify({'error': 'Method not found'}), 404

@app.route('/sync', methods=['POST'])
def sync():
    block = request.json
    if not block:
        return jsonify({'error': 'No block provided'}), 400
    log.info(f"[SYNC] Received block index={block.get('index')} hash={block.get('hash')} from {request.remote_addr}")
    remote = request.remote_addr
    if remote:
        try:
            peer_url = node_url_from_addr(remote)
            add_peer(peer_url)
            log.info(f"[PEER] Auto-added peer {peer_url}")
        except Exception:
            pass
    chain = load_chain()
    wallets = load_wallets()
    if len(chain) == 0:
        chain.append(block)
        save_chain(chain)
        update_wallets_from_chain(chain)
        log.info("[SYNC] Genesis block accepted")
        return jsonify({'result': 'Genesis block accepted'})
    last_block = chain[-1]
    try:
        if is_block_valid(block, last_block, wallets):
            log.info("[SYNC] Block valid. Appending.")
            chain.append(block)
            save_chain(chain)
            update_wallets_from_chain(chain)
            for p in load_peers():
                try:
                    requests.post(f"{node_url_from_addr(p)}/sync", json=block, timeout=RPC_TIMEOUT)
                except Exception:
                    continue
            return jsonify({'result': 'Block accepted'})
        else:
            log.warning("[SYNC] Received invalid block; will attempt full sync")
            replaced = auto_sync_from_peers()
            if replaced:
                return jsonify({'result': 'Local chain replaced via full sync'}), 200
            return jsonify({'error': 'Invalid block and sync failed'}), 400
    except Exception as e:
        log.exception(f"[SYNC] Exception processing block: {e}")
        return jsonify({'error': 'Exception processing block'}), 500

@app.route('/add_peer', methods=['POST'])
def add_peer_route():
    data = request.json or {}
    peer_url = data.get('url')
    if not peer_url:
        return jsonify({'error': 'No peer url provided'}), 400
    try:
        normalized = node_url_from_addr(peer_url)
        add_peer(normalized)
        log.info(f"[PEER] Added peer {normalized}")
        try:
            self_url = get_self_url()
            requests.post(f"{normalized}/add_peer", json={"url": self_url}, timeout=RPC_TIMEOUT)
            log.info(f"[PEER] Sent reciprocal add_peer to {normalized}")
        except Exception:
            log.debug(f"[PEER] Reciprocal add_peer to {normalized} failed (nonfatal)")
        return jsonify({'result': 'Peer added'})
    except Exception as e:
        log.exception(f"[PEER] Failed to add peer {peer_url}: {e}")
        return jsonify({'error': 'Failed to add peer'}), 500

@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify(load_peers())

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify(load_chain())

# ======================= Helper =======================
def calculate_balance(address):
    chain = load_chain()
    balance = 0
    for block in chain:
        for tx in block.get('transactions', []):
            sender = tx.get('from')
            to = tx.get('to') if 'to' in tx else (tx.get('data') or {}).get('to')
            value = tx.get('value') if 'value' in tx else (tx.get('data') or {}).get('value', 0)
            if sender == address:
                balance -= value
            if to == address:
                balance += value
    return balance

# ======================= Run server =======================
def run_server():
    try:
        bootstrap_peers()
    except Exception:
        log.exception("[BOOT] bootstrap_peers error")
    try:
        auto_sync_from_peers()
    except Exception:
        log.exception("[SYNC] initial auto_sync failed")
    start_background_sync()
    app.run(host="0.0.0.0", port=NODE_PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()
