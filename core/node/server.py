# core/node/server.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, request, jsonify
from chain.blockchain import mine_block, save_chain, load_chain
from chain.tx_pool import add_transaction, load_tx_pool
from node.peers import load_peers, add_peer
from wallet.wallet import verify_signature

app = Flask(__name__)

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

# === RPC endpoint ===
@app.route('/rpc', methods=['POST'])
def rpc():
    data = request.json
    method = data.get('method')
    params = data.get('params', [])

    if method == 'wcn_blockNumber':
        return jsonify({'result': hex(len(load_chain()))})

    elif method == 'wcn_mineBlock':
        miner = params[0]
        block = mine_block(miner, [])
        return jsonify({'result': block})

    elif method == 'wcn_getBalance':
        address = params[0]
        return jsonify({'result': calculate_balance(address)})

    elif method == 'wcn_sendTransaction':
        tx = params[0]
        public_key = tx.get("publicKey")
        if not public_key or not verify_signature(tx['data'], tx['signature'], public_key):
            return jsonify({'error': 'Invalid signature'}), 400

        add_transaction(tx)
        return jsonify({'result': 'Transaction added to pool'})

    return jsonify({'error': 'Method not found'}), 404

# === SYNC antar node ===
@app.route('/sync', methods=['POST'])
def sync():
    block = request.json
    chain = load_chain()

    if len(chain) == 0:
        chain.append(block)
        save_chain(chain)
        return jsonify({'result': 'Genesis block accepted'})

    if block['previous_hash'] == chain[-1]['hash']:
        chain.append(block)
        save_chain(chain)
        return jsonify({'result': 'Block accepted'})

    return jsonify({'error': 'Invalid block'}), 400

# === Add peer endpoint ===
@app.route('/add_peer', methods=['POST'])
def add_peer_route():
    data = request.json
    peer_url = data.get('url')
    add_peer(peer_url)
    return jsonify({'result': 'Peer added'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
#Terkadang perasaan itu harus di debug, agar kita tahu apakah dia juga memiliki rasa?
