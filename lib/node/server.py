# core/node/server.py
import os, sys, requests, logging
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'lib' )))
from flask import Flask, request, jsonify
#from app.config import DATA_DIR
from lib.chain.blockchain import mine_block, save_chain, load_chain, is_block_valid, update_wallets_from_chain
from lib.chain.tx_pool import add_transaction, load_tx_pool
from lib.node.peers import load_peers, add_peer
from lib.wallet.wallet import verify_signature, load_wallets

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger()

app = Flask(__name__)
# kalkulasikan saldo
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
# auto sync dari peer
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


# === Full Chain ===
@app.route('/fullchain', methods=['GET'])
def full_chain():
    return jsonify({
        'length': len(load_chain()),
        'chain': load_chain()
    })

# === RPC endpoint ===
@app.route('/rpc', methods=['POST'])
def rpc():
    data = request.json
    method = data.get('method')
    params = data.get('params', [])
    log.info(f"RPC Method Called: {method} | Params: {params}")


    if method == 'wcn_blockNumber':
        return jsonify({'result': hex(len(load_chain()))})

    elif method == 'wcn_mineBlock':
        miner = params[0]
        block = mine_block(miner, [])
        log.info(f"[⛏️] Mined block by {miner} with hash {block['hash']}")


        # Broadcast ke semua peers
        for peer in load_peers():
            try:
                requests.post(f"{peer}/sync", json=block, timeout=2)
            except Exception:
                continue  
        return jsonify({'result': block})

    elif method == 'wcn_getBalance':
        address = params[0]
        return jsonify({'result': calculate_balance(address)})

    elif method == 'wcn_sendTransaction':
        tx = params[0]
        public_key = tx.get("publicKey")
        sender = tx.get("from")
        to = tx["data"]["to"]
        value = tx["data"]["value"]
        log.info(f"[TX] Received transaction from {sender} to {to} amount {value}")

        # validasikan signature 
        if not public_key or not verify_signature(tx['data'], tx['signature'], public_key):
            
            log.warning(f"[TX] Invalid signature from {sender}")
            return jsonify({'error': 'Invalid signature'}), 400

        # validasikan saldo apakah cukup? jangan sampai saldo tidak cukup seperti kamu yang tidak cukup perhatian anjay
        balance = calculate_balance(sender)
        if balance < value:

            log.warning(f"[TX] Insufficient balance for {sender}: has {balance}, needs {value}")
            return jsonify({'error': f'Insufficient balance. Available: {balance}'}), 400

        # tambah ke pool transaksi seperti menambahkannya ke dalam hatimu 
        log.info(f"[TX] Transaction accepted from {sender}")
        add_transaction(tx)
        return jsonify({'result': 'Transaction added to pool'})


    return jsonify({'error': 'Method not found'}), 404

# === SYNC antar node ===
@app.route('/sync', methods=['POST'])
def sync():
    block = request.json
    log.info(f"[SYNC] Received block {block['index']} with hash {block['hash']}")
    chain = load_chain()
    wallets = load_wallets()

    # Handle genesis block
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
        return jsonify({'result': 'Block accepted'})
    else:
        log.warning("[SYNC] Invalid block received. Trying auto-sync from peer...")

        # Auto-sync logic
        peer_ip = request.remote_addr
        try:
            response = requests.get(f"http://{peer_ip}:8000/fullchain", timeout=3)
            peer_chain = response.json().get('chain', [])
            peer_length = response.json().get('length', 0)

            if peer_chain and peer_length > len(chain):
                save_chain(peer_chain)
                update_wallets_from_chain(peer_chain)
                log.info("[SYNC] Local chain replaced by longer chain from peer.")
                return jsonify({'result': 'Synced from peer'}), 200
            else:
                log.warning("[SYNC] Peer chain not longer or invalid.")
        except Exception as e:
            log.error(f"[SYNC] Failed to fetch chain from peer: {e}")

        return jsonify({'error': 'Invalid block'}), 400

    #return jsonify({'error': 'Invalid block'}), 400

# === Add peer endpoint ===
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

# === GET peers endpoint ===
@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify(load_peers())

# === Get chain endpoint === 
@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify(load_chain())



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
#Terkadang perasaan itu harus di debug, agar kita tahu apakah dia juga memiliki rasa?
