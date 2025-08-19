# lib/node/server.py
import os
import sys
import requests
import logging
import time
import threading
from flask import Flask, request, jsonify

# make project root importable (so imports like lib.chain.* work)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lib.chain.blockchain import (
    mine_block, save_chain, load_chain, is_block_valid, update_wallets_from_chain, MAX_SUPPLY, hash_block
)
from lib.chain.tx_pool import add_transaction, load_tx_pool, save_tx_pool
from lib.node.peers import load_peers, add_peer, save_peers
from lib.wallet.wallet import verify_signature, load_wallets, save_wallets
#from lib.node.server import start_server as run_server
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
SYNC_INTERVAL = 10  # seconds between background sync attempts
RPC_TIMEOUT = 3     # seconds for peer HTTP calls
NODE_PORT = 8000    # default port peers run on; used to auto-build peer URL if missing

# ======================= Helper utils =======================
def node_url_from_addr(addr):
    # addr may be "127.0.0.1" or "host:port". Normalize to http://host:port
    if addr.startswith("http://") or addr.startswith("https://"):
        return addr
    if ":" in addr:
        return f"http://{addr}"
    return f"http://{addr}:{NODE_PORT}"

def validate_chain_structure(chain):
    """
    Validate chain integrity:
    - prev hash linkage
    - block hashes correct (using hash_block)
    - basic transaction signature validation and balance simulation
    Returns True/False
    """
    try:
        wallets_master = load_wallets()
        # create address->balance map from wallets_master (copy)
        address_map = {w['address']: {'balance': w.get('balance', 0)} for w in wallets_master}
        for i, block in enumerate(chain):
            # hash check
            computed = hash_block(block)
            if block.get('hash') != computed:
                log.warning(f"[VALIDATE] Block {i} hash mismatch (stored {block.get('hash')} != computed {computed})")
                return False
            # prev hash
            if i > 0:
                if block.get('previous_hash') != chain[i-1].get('hash'):
                    log.warning(f"[VALIDATE] Block {i} previous_hash mismatch")
                    return False
            # difficulty check (reuse same prefix logic)
            if not block.get('hash', '').startswith('0000'):
                log.warning(f"[VALIDATE] Block {i} doesn't meet difficulty prefix")
                return False
            # validate transactions signatures and balances
            for tx in block.get('transactions', []):
                if tx.get('from') == 'COINBASE':
                    # coinbase outputs add balance to receiver later
                    to_addr = tx.get('to')
                    amount = tx.get('value', 0)
                    address_map.setdefault(to_addr, {'balance': 0})
                    address_map[to_addr]['balance'] += amount
                    continue
                # others: validate signature
                txdata = tx.get('data')
                sig = tx.get('signature')
                pub = tx.get('publicKey') or tx.get('public_key') or None
                if not txdata or not sig or not pub:
                    log.warning(f"[VALIDATE] Missing signature/pub/txdata in tx in block {i}")
                    return False
                # verify signature (wallet.verify_signature expects json tx & signature & pub hex)
                if not verify_signature(txdata, tx['signature'], pub):
                    log.warning(f"[VALIDATE] Bad signature in block {i}")
                    return False
                sender = tx.get('from')
                value = txdata.get('value', 0)
                to_addr = txdata.get('to')
                # check sender balance
                address_map.setdefault(sender, {'balance': 0})
                if address_map[sender]['balance'] < value:
                    log.warning(f"[VALIDATE] Insufficient balance for {sender} in simulated state")
                    return False
                address_map[sender]['balance'] -= value
                address_map.setdefault(to_addr, {'balance': 0})
                address_map[to_addr]['balance'] += value
        return True
    except Exception as e:
        log.exception(f"[VALIDATE] Exception validating chain: {e}")
        return False

# ======================= Auto-sync logic =======================
def auto_sync_from_peers():
    """
    Query all peers, find the longest *valid* chain, replace local chain if longer.
    """
    peers = load_peers()
    if not peers:
        log.debug("[SYNC] No peers to sync from.")
        return False

    local_chain = load_chain()
    best_chain = local_chain
    best_len = len(local_chain)
    replaced = False

    for peer in peers:
        peer_url = node_url_from_addr(peer)
        try:
            res = requests.get(f"{peer_url}/fullchain", timeout=RPC_TIMEOUT)
            if res.status_code != 200:
                log.debug(f"[SYNC] Peer {peer} returned status {res.status_code}")
                continue
            data = res.json()
            new_chain = data.get('chain', [])
            new_len = data.get('length', len(new_chain))
            if new_len <= best_len:
                continue
            # validate new chain
            if validate_chain_structure(new_chain):
                best_chain = new_chain
                best_len = new_len
                log.info(f"[SYNC] Found longer valid chain from {peer} length={new_len}")
            else:
                log.warning(f"[SYNC] Peer {peer} chain failed validation")
        except Exception as e:
            log.warning(f"[SYNC] Failed fetching from {peer}: {e}")

    if best_len > len(local_chain):
        save_chain(best_chain)
        update_wallets_from_chain(best_chain)
        log.info(f"[SYNC] Replaced local chain with chain length {best_len}")
        replaced = True

    return replaced

def periodic_sync():
    while True:
        try:
            auto_sync_from_peers()
        except Exception:
            log.exception("[SYNC] periodic_sync exception")
        time.sleep(SYNC_INTERVAL)

# start background sync thread when app starts
def start_background_sync():
    t = threading.Thread(target=periodic_sync, daemon=True)
    t.start()

# ======================= Flask endpoints =======================
@app.route("/")
def home():
    return {"status": "running"}

@app.route('/fullchain', methods=['GET'])
def full_chain():
    chain = load_chain()
    return jsonify({
        'length': len(chain),
        'chain': chain
    })

@app.route('/rpc', methods=['POST'])
def rpc():
    data = request.json or {}
    method = data.get('method')
    params = data.get('params', [])
    log.info(f"[RPC] {method} params={params}")

    if method == 'wcn_blockNumber':
        return jsonify({'result': hex(len(load_chain()))})

    elif method == 'wcn_mineBlock':
        # allow miner param to be either single address or list
        miners = params if isinstance(params, list) else [params[0]] if params else []
        if not miners:
            return jsonify({'error': 'No miner address provided'}), 400
        block = mine_block(miners, [])
        reward_total = sum(tx.get('value', 0) for tx in block.get('transactions', []) if tx.get('from') == 'COINBASE')
        log.info(f"[MINE] Mined block idx={block.get('index')} hash={block.get('hash')} reward={reward_total}")
        # after mining broadcast to peers
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
        balance = calculate_balance(address=address)
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
        MIN_FEE = 50_000
        if value is None:
            return jsonify({'error': 'Invalid tx data'}), 400
        if value < MIN_TRANSFER:
            return jsonify({'error': f'Transfer too small. Minimum is {MIN_TRANSFER}'}), 400

        fee = tx.get('fee', MIN_FEE)
        tx['fee'] = fee

        if not public_key or not verify_signature(tx['data'], tx['signature'], public_key):
            log.warning("[TX] Invalid signature")
            return jsonify({'error': 'Invalid signature'}), 400

        balance = calculate_balance(sender)
        if balance < (value + fee):
            log.warning(f"[TX] Insufficient balance for {sender}: have {balance}, need {value+fee}")
            return jsonify({'error': 'Insufficient balance including fee', 'available': balance}), 400

        add_transaction(tx)
        log.info(f"[TX] Transaction accepted {sender} -> {to} fee={fee}")
        return jsonify({'result': 'Transaction added to pool', 'fee': fee})

    else:
        return jsonify({'error': 'Method not found'}), 404

@app.route('/sync', methods=['POST'])
def sync():
    # when peer posts a block we should try to append if valid, otherwise try to sync full chain
    block = request.json
    if not block:
        return jsonify({'error': 'No block provided'}), 400
    log.info(f"[SYNC] Received block index={block.get('index')} hash={block.get('hash')} from {request.remote_addr}")

    # auto-add peer to peerlist (use remote addr)
    remote = request.remote_addr
    if remote:
        peer_url = node_url_from_addr(remote)
        try:
            add_peer(peer_url)
            log.info(f"[PEER] Auto-added peer {peer_url}")
        except Exception:
            pass

    chain = load_chain()
    wallets = load_wallets()

    # genesis case
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
            # broadcast to peers so others can sync
            for p in load_peers():
                try:
                    requests.post(f"{node_url_from_addr(p)}/sync", json=block, timeout=RPC_TIMEOUT)
                except Exception:
                    continue
            return jsonify({'result': 'Block accepted'})
        else:
            log.warning("[SYNC] Received invalid block; will attempt full sync from peers")
            # attempt full sync
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
    # normalize
    try:
        add_peer(peer_url)
        log.info(f"[PEER] Added peer {peer_url}")
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

# helper to calculate balance (same logic as before)
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
def run_server():
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
# ======================= App start =======================
if __name__ == '__main__':
    # start background sync thread
    start_background_sync()
    run_server()
