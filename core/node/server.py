# core/node/server.py
from flask import Flask, request, jsonify
from chain.blockchain import mine_block, load_chain
from chain.tx_pool import add_transaction, load_tx_pool
from wallet.wallet import load_wallets, verify_signature


app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(port=8000)
