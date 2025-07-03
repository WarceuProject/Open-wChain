# core/node/server.py
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Flask, request, jsonify
from chain.blockchain import mine_block, save_chain, load_chain, update_wallets_from_chain
from chain.tx_pool import add_transaction, load_tx_pool
from node.peers import load_peers, add_peer
from wallet.wallet import load_wallets, verify_signature


app = Flask(__name__)
#RPC
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
        wallets = load_wallets()
        wallet = next((w for w in wallets if w['address'] == address), None)
        return jsonify({'result': wallet['balance'] if wallet else 0})

    elif method == 'wcn_sendTransaction':
        tx = params[0]
        wallets = load_wallets()
        sender = next((w for w in wallets if w['address'] == tx['from']), None)

        if not sender:
            return jsonify({'error': 'Sender not found'}), 400

        if not verify_signature(tx['data'], tx['signature'], sender['publicKey']):
            return jsonify({'error': 'Invalid signature'}), 400

        add_transaction(tx)
        return jsonify({'result': 'Transaction added to pool'})


    else:
        return jsonify({'error': 'Method not found'}), 404

#SYNC P2P
@app.route('/sync', methods=['POST'])
def sync():
    block = request.json
    chain = load_chain()

    if len(chain) == 0:
        chain.append(block)
        save_chain(chain)
        update_wallets_from_chain(chain)
        return jsonify({'result': 'Genesis block accepted'})

    if block['previous_hash'] == chain[-1]['hash']:
        chain.append(block)
        save_chain(chain)
        update_wallets_from_chain(chain)
        return jsonify({'result': 'Block accepted'})

    return jsonify({'error': 'Invalid block'}), 400
#SYNC P2P - add_peer
@app.route('/add_peer', methods=['POST'])
def add_peer_route():
    data = request.json
    peer_url = data.get('url')
    add_peer(peer_url)
    return jsonify({'result': 'Peer added'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
