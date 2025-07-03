# openwchain/node/server.py
from flask import Flask, request, jsonify
from chain.blockchain import mine_block, load_chain
from wallet.wallet import load_wallets

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
        from wallet.wallet import verify_signature
        is_valid = verify_signature(tx['data'], tx['signature'], sender['publicKey'])
        if not is_valid:
            return jsonify({'error': 'Invalid signature'}), 400
        return jsonify({'result': 'Transaction received (not yet mined)'})

    else:
        return jsonify({'error': 'Method not found'}), 404

if __name__ == '__main__':
    app.run(port=8000)
