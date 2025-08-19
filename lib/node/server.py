# lib/node/server.py
import os, sys, requests, logging, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib')))
from flask import Flask, request, jsonify

from lib.chain.blockchain import (
    mine_block, save_chain, load_chain, is_block_valid, update_wallets_from_chain, MAX_SUPPLY
)
from lib.chain.tx_pool import add_transaction, load_tx_pool, save_tx_pool
from lib.node.peers import load_peers, add_peer
from lib.wallet.wallet import verify_signature, load_wallets

# ======================= Logging =======================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger()

# ======================= Flask App =======================
app = Flask(__name__)

@app.route("/")
def home():
    return {"status": "running"}

# ======================= Balance =======================
def calculate_balance(address):
    chain = load_chain()
    balance = 0
    for block in chain:
        for tx in block['transactions']:
            sender = tx.get('from')
            to = tx['to'] if 'to' in tx else tx['data']['to']
            value = tx['value'] if 'value' in tx else tx['data']['value']
            if sender == address:
                balance -= value
            if to == address:
                balance += value
    return balance

# ======================= Auto-sync =======================
def auto_sync_from_peer():
    for peer in load_peers():
        try:
            res = requests.get(f"{peer}/fullchain", timeout=2)
            data = res.json()
            new_chain = data['chain']
            if len(new_chain) > len(load_chain()):
                save_chain(new_chain)
                update_wallets_from_chain(new_chain)
                log.info(f"[SYNC] Chain replaced from peer {peer}")
                return True
        except Exception as e:
            log.warning(f"[SYNC] Failed to sync from {peer}: {e}")
    return False

# ======================= Full Chain =======================
@app.route('/fullchain', methods=['GET'])
def full_chain():
    return jsonify({
        'length': len(load_chain()),
        'chain': load_chain()
    })

# ======================= RPC Endpoint =======================
@app.route('/rpc', methods=['POST'])
def rpc():
    data = request.json
    method = data.get('method')
    params = data.get('params', [])
    log.info(f"RPC Method Called: {method} | Params: {params}")

    # ----------------- Block Number -----------------
    if method == 'wcn_blockNumber':
        return jsonify({'result': hex(len(load_chain()))})

    # ----------------- Mine Block -----------------
    elif method == 'wcn_mineBlock':
        miners = params if isinstance(params, list) else [params[0]]
        # Mine block dengan multi-miner support
        block = mine_block(miners, [])
        # Hitung total reward yang masuk ke miners
        reward_total = sum(
            tx['value'] for tx in block['transactions'] if tx['from'] == 'COINBASE'
        )
        log.info(f"[⛏️] Mined block by {miners} with hash {block['hash']} | Reward distributed: {reward_total}")
        return jsonify({'result': block, 'reward': reward_total})

    # ----------------- Get Balance -----------------
    elif method == 'wcn_getBalance':
        address = params[0]
        return jsonify({'result': calculate_balance(address)})

    # ----------------- Send Transaction -----------------
    elif method == 'wcn_sendTransaction':
        tx = params[0]
        public_key = tx.get("publicKey")
        sender = tx.get("from")
        to = tx["data"]["to"]
        value = tx["data"]["value"]
        log.info(f"[TX] Received transaction from {sender} to {to} amount {value}")

        MIN_TRANSFER = 100_000
        MIN_FEE = 50_000
        if value < MIN_TRANSFER:
            return jsonify({'error': f'Transfer too small. Minimum is {MIN_TRANSFER}'}), 400
        fee = tx.get('fee', MIN_FEE)
        tx['fee'] = fee

        if not public_key or not verify_signature(tx['data'], tx['signature'], public_key):
            log.warning(f"[TX] Invalid signature from {sender}")
            return jsonify({'error': 'Invalid signature'}), 400

        balance = calculate_balance(sender)
        if balance < (value + fee):
            log.warning(f"[TX] Insufficient balance for {sender}: has {balance}, needs {value + fee}")
            return jsonify({'error': f'Insufficient balance including fee. Available: {balance}'}), 400

        add_transaction(tx)
        log.info(f"[TX] Transaction accepted from {sender} | Fee: {fee}")
        return jsonify({'result': 'Transaction added to pool', 'fee': fee})

    return jsonify({'error': 'Method not found'}), 404

# ======================= Sync =======================
@app.route('/sync', methods=['POST'])
def sync():
    block = request.json
    log.info(f"[SYNC] Received block {block['index']} with hash {block['hash']}")
    chain = load_chain()
    wallets = load_wallets()

    if len(chain) == 0:
        log.info("[SYNC] Accepting genesis block")
        chain.append(block)
        save_chain(chain)
        update_wallets_from_chain(chain)
        return jsonify({'result': 'Genesis block accepted'})

    last_block = chain[-1]
    if is_block_valid(block, last_block, wallets):
        log.info("[SYNC] Block is valid. Appending to chain.")
        chain.append(block)
        save_chain(chain)
        update_wallets_from_chain(chain)
        auto_sync_from_peer()
        return jsonify({'result': 'Block accepted'})
    else:
        log.warning("[SYNC] Invalid block received. Trying auto-sync from peer...")
        auto_sync_from_peer()
        return jsonify({'error': 'Invalid block'}), 400

# ======================= Peers =======================
@app.route('/add_peer', methods=['POST'])
def add_peer_route():
    data = request.json
    peer_url = data.get('url')
    if not peer_url or not peer_url.startswith("http"):
        log.warning(f"[PEER] Invalid peer URL attempted: {peer_url}")
        return jsonify({'error': 'Invalid peer URL'}), 400
    add_peer(peer_url)
    log.info(f"[PEER] Added peer: {peer_url}")
    return jsonify({'result': 'Peer added'})

@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify(load_peers())

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify(load_chain())

# ======================= Run Server =======================
def run_server():
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()
