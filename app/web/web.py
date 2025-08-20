import os, sys, json, hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort

# allow importing project packages
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lib.chain.blockchain import load_chain, MAX_SUPPLY
from lib.chain.tx_pool import load_tx_pool
from lib.wallet.wallet import load_wallets

app = Flask(__name__, template_folder='templates', static_folder='static')
UNIT = 100_000_000  # 1 WCN = 100_000_000 units

# --- UTILITIES ---
def tx_id(tx):
    s = json.dumps(tx, sort_keys=True).encode()
    return hashlib.sha256(s).hexdigest()

def format_time(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)

def sats_to_wcn(v):
    return (v or 0) / UNIT

def format_wcn_units(v):
    return "{:,.8f}".format(sats_to_wcn(v or 0))

def find_tx_in_chain(txid):
    chain = load_chain()
    for block in chain:
        for tx in block.get('transactions', []):
            if tx_id(tx) == txid:
                return tx, block
    return None, None

def find_address_txs(address):
    chain = load_chain()
    results = []
    for block in chain:
        for tx in block.get('transactions', []):
            frm = tx.get('from')
            to = tx.get('to') if 'to' in tx else (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else None)
            if frm == address or to == address:
                results.append({'tx': tx, 'block': block})
    # pending mempool
    pool = load_tx_pool()
    for tx in pool:
        frm = tx.get('from')
        to = tx.get('to') if 'to' in tx else (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else None)
        if frm == address or to == address:
            results.append({'tx': tx, 'block': None})
    return results

def calculate_balance_from_chain(address):
    chain = load_chain()
    balance = 0
    for block in chain:
        for tx in block.get('transactions', []):
            sender = tx.get('from')
            to = tx.get('to') if 'to' in tx else (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else None)
            value = tx.get('value') if 'value' in tx else (tx.get('data', {}).get('value') if isinstance(tx.get('data'), dict) else 0)
            fee = tx.get('fee', 0)
            if sender == address:
                balance -= (value + fee)
            if to == address:
                balance += value
    return balance

# --- ROUTES ---
@app.route('/', methods=['GET'])
def index():
    chain = load_chain()
    blocks = list(reversed(chain))[:10]  # latest 10 blocks
    mempool = load_tx_pool()
    txs = []
    # last 10 tx from chain
    for block in reversed(chain):
        for tx in reversed(block.get('transactions', [])):
            txs.append({'tx': tx, 'block': block})
            if len(txs) >= 10:
                break
        if len(txs) >= 10:
            break

    block_summary = []
    for b in blocks:
        reward_total = sum(tx.get('value', 0) + tx.get('fee', 0) for tx in b.get('transactions', []) if tx.get('from') == 'COINBASE')
        block_summary.append({
            'index': b.get('index'),
            'hash': b.get('hash'),
            'time': format_time(b.get('timestamp')),
            'tx_count': len(b.get('transactions', [])),
            'validator': b.get('miner', 'N/A'),
            'reward_wcn': format_wcn_units(reward_total)
        })

    tx_summary = []
    for item in txs:
        tx = item['tx']
        blk = item['block']
        data = tx.get('data', {})
        tx_summary.append({
            'txid': tx_id(tx),
            'time': format_time(tx.get('timestamp') or data.get('timestamp')),
            'from': tx.get('from'),
            'to': data.get('to') or tx.get('to'),
            'amount_wcn': format_wcn_units(data.get('value') or tx.get('value', 0)),
            'fee_wcn': format_wcn_units(tx.get('fee', 0))
        })

    total_units = sum(tx.get('value', 0) for block in chain for tx in block.get('transactions', []))

    return render_template('index.html',
        blocks=block_summary,
        last_txs=tx_summary,
        total_blocks=len(chain),
        max_supply=format_wcn_units(MAX_SUPPLY),
        circulating=format_wcn_units(total_units),
        mempool_size=len(mempool)
    )

@app.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))
    # block index
    if q.isdigit():
        return redirect(url_for('block_view', index=int(q)))
    # block hash
    chain = load_chain()
    for b in chain:
        if b.get('hash', '').startswith(q):
            return redirect(url_for('block_view', index=b.get('index')))
    # txid
    for b in chain:
        for tx in b.get('transactions', []):
            if tx_id(tx).startswith(q):
                return redirect(url_for('tx_view', txid=tx_id(tx)))
    # address
    if q.startswith('W'):
        wallets = load_wallets()
        for w in wallets:
            if w['address'] == q:
                return redirect(url_for('address_view', address=q))
    return render_template('notfound.html', query=q), 404

@app.route('/block/<int:index>', methods=['GET'])
def block_view(index):
    chain = load_chain()
    if index < 0 or index >= len(chain):
        abort(404)
    b = chain[index]
    txs = []
    for tx in b.get('transactions', []):
        t = dict(tx)
        t['txid'] = tx_id(tx)
        t['from_display'] = tx.get('from')
        t['to_display'] = (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else tx.get('to'))
        t['value_units'] = (tx.get('data', {}).get('value') if isinstance(tx.get('data'), dict) else tx.get('value', 0))
        t['fee_units'] = tx.get('fee', 0)
        t['value_wcn'] = format_wcn_units(t['value_units'])
        t['fee_wcn'] = format_wcn_units(t['fee_units'])
        txs.append(t)
    reward_total = sum(tx.get('value', 0) + tx.get('fee', 0) for tx in b.get('transactions', []) if tx.get('from') == 'COINBASE')
    return render_template('block.html', block=b, txs=txs, reward_wcn=format_wcn_units(reward_total), format_time=format_time)

@app.route('/tx/<txid>', methods=['GET'])
def tx_view(txid):
    tx, block = find_tx_in_chain(txid)
    if not tx:
        abort(404)
    t = dict(tx)
    t['txid'] = txid
    t['from_display'] = tx.get('from')
    t['to_display'] = (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else tx.get('to'))
    t['value_units'] = (tx.get('data', {}).get('value') if isinstance(tx.get('data'), dict) else tx.get('value', 0))
    t['fee_units'] = tx.get('fee', 0)
    t['value_wcn'] = format_wcn_units(t['value_units'])
    t['fee_wcn'] = format_wcn_units(t['fee_units'])
    return render_template('tx.html', tx=t, block=block, format_time=format_time)

@app.route('/address/<address>', methods=['GET'])
def address_view(address):
    if not address.startswith('W') or len(address) < 6:
        abort(404)
    txs = find_address_txs(address)
    balance_wcn = format_wcn_units(calculate_balance_from_chain(address))
    tx_list = []
    for item in txs:
        tx = item['tx']
        blk = item['block']
        entry = dict(tx)
        entry['txid'] = tx_id(tx)
        entry['from_display'] = tx.get('from')
        entry['to_display'] = (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else tx.get('to'))
        entry['value_units'] = (tx.get('data', {}).get('value') if isinstance(tx.get('data'), dict) else tx.get('value', 0))
        entry['fee_units'] = tx.get('fee', 0)
        entry['value_wcn'] = format_wcn_units(entry['value_units'])
        entry['fee_wcn'] = format_wcn_units(entry['fee_units'])
        entry['block_index'] = blk.get('index') if blk else None
        tx_list.append(entry)
    return render_template('address.html', address=address, balance=balance_wcn, txs=tx_list, format_time=format_time)

@app.errorhandler(404)
def not_found(e):
    return render_template('notfound.html', query=None), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
