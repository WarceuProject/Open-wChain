# app/web/explorer.py
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

# utility to search tx by id or address involvement
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
            # normalize tx fields
            frm = tx.get('from')
            to = tx.get('to') if 'to' in tx else (tx.get('data', {}) .get('to') if isinstance(tx.get('data'), dict) else None)
            if frm == address or to == address:
                results.append({'tx': tx, 'block': block})
    # pending mempool
    pool = load_tx_pool()
    for tx in pool:
        frm = tx.get('from')
        to = tx.get('to') if 'to' in tx else (tx.get('data', {}) .get('to') if isinstance(tx.get('data'), dict) else None)
        if frm == address or to == address:
            results.append({'tx': tx, 'block': None})
    return results

def calculate_balance_from_chain(address):
    chain = load_chain()
    balance = 0
    # iterate blocks & tx
    for block in chain:
        for tx in block.get('transactions', []):
            sender = tx.get('from')
            to = tx.get('to') if 'to' in tx else (tx.get('data', {}) .get('to') if isinstance(tx.get('data'), dict) else None)
            value = tx.get('value') if 'value' in tx else (tx.get('data', {}) .get('value') if isinstance(tx.get('data'), dict) else 0)
            if sender == address:
                balance -= value
            if to == address:
                balance += value
    return balance

@app.route('/', methods=['GET'])
def index():
    chain = load_chain()
    # newest first
    blocks = list(reversed(chain))
    summary = []
    total_txs = 0
    for b in blocks:
        txs = b.get('transactions', [])
        reward_total = sum(tx.get('value', 0) for tx in txs if tx.get('from') == 'COINBASE')
        tx_count = len(txs)
        total_txs += tx_count
        summary.append({
            'index': b.get('index'),
            'hash': b.get('hash'),
            'time': format_time(b.get('timestamp')),
            'tx_count': tx_count,
            'reward_units': reward_total,
            'reward_wcn': format_wcn_units(reward_total)
        })

    # compute circulating supply (simple sum of outputs in chain)
    total_units = sum(tx.get('value', 0) for block in chain for tx in block.get('transactions', []))
    mempool = load_tx_pool()

    return render_template('index.html',
        blocks=summary,
        total_blocks=len(chain),
        total_txs=total_txs,
        mempool_size=len(mempool),
        max_supply_wcn=format_wcn_units(MAX_SUPPLY),
        circulating_wcn=format_wcn_units(total_units)
    )

# search box handler
@app.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))

    # txid: 64 hex
    if len(q) == 64 and all(c in '0123456789abcdefABCDEF' for c in q):
        return redirect(url_for('tx_view', txid=q.lower()))
    # block index number?
    if q.isdigit():
        return redirect(url_for('block_view', index=int(q)))
    # address (we use W prefix in wallet)
    if q.startswith('W') and len(q) > 5:
        return redirect(url_for('address_view', address=q))
    # as fallback check block hash prefix or txid prefix
    # try search in chain for block hash starting with q
    chain = load_chain()
    for b in chain:
        if b.get('hash', '').startswith(q):
            return redirect(url_for('block_view', index=b.get('index')))
    # try tx prefix
    for b in chain:
        for tx in b.get('transactions', []):
            if tx_id(tx).startswith(q):
                return redirect(url_for('tx_view', txid=tx_id(tx)))
    # not found
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
        if 'data' in t and isinstance(t['data'], dict):
            t['from_display'] = t.get('from')
            t['to_display'] = t['data'].get('to')
            t['value_units'] = t['data'].get('value')
            t['fee_units'] = t['data'].get('fee', None)
        else:
            t['from_display'] = t.get('from')
            t['to_display'] = t.get('to')
            t['value_units'] = t.get('value', 0)
            t['fee_units'] = t.get('fee', None)
        t['value_wcn'] = format_wcn_units(t['value_units'])
        t['fee_wcn'] = format_wcn_units(t['fee_units']) if t['fee_units'] is not None else None
        txs.append(t)

    reward_total = sum(tx.get('value', 0) for tx in b.get('transactions', []) if tx.get('from') == 'COINBASE')
    return render_template('block.html', block=b, txs=txs, reward_wcn=format_wcn_units(reward_total), format_time=format_time)

@app.route('/tx/<txid>', methods=['GET'])
def tx_view(txid):
    tx, block = find_tx_in_chain(txid)
    mempool_flag = False
    if not tx:
        # check mempool
        pool = load_tx_pool()
        for p in pool:
            if tx_id(p) == txid:
                tx = p
                block = None
                mempool_flag = True
                break
    if not tx:
        abort(404)
    t = dict(tx)
    t['txid'] = txid
    if 'data' in t and isinstance(t['data'], dict):
        t['from_display'] = t.get('from')
        t['to_display'] = t['data'].get('to')
        t['value_units'] = t['data'].get('value')
        t['fee_units'] = t['data'].get('fee', None)
        t['timestamp'] = t['data'].get('timestamp')
    else:
        t['from_display'] = t.get('from')
        t['to_display'] = t.get('to')
        t['value_units'] = t.get('value', 0)
        t['fee_units'] = t.get('fee', None)
        t['timestamp'] = t.get('timestamp', None)
    t['value_wcn'] = format_wcn_units(t['value_units'])
    t['fee_wcn'] = format_wcn_units(t['fee_units']) if t['fee_units'] is not None else None

    return render_template('tx.html', tx=t, block=block, mempool=mempool_flag, format_time=format_time)

@app.route('/mempool', methods=['GET'])
def mempool_view():
    pool = load_tx_pool()
    txs = []
    for tx in pool:
        t = dict(tx)
        t['txid'] = tx_id(tx)
        if 'data' in t and isinstance(t['data'], dict):
            t['from_display'] = t.get('from')
            t['to_display'] = t['data'].get('to')
            t['value_units'] = t['data'].get('value')
            t['fee_units'] = t['data'].get('fee', None)
            t['timestamp'] = t['data'].get('timestamp')
        else:
            t['from_display'] = t.get('from')
            t['to_display'] = t.get('to')
            t['value_units'] = t.get('value', 0)
            t['fee_units'] = t.get('fee', None)
            t['timestamp'] = t.get('timestamp', None)
        t['value_wcn'] = format_wcn_units(t['value_units'])
        t['fee_wcn'] = format_wcn_units(t['fee_units']) if t['fee_units'] is not None else None
        txs.append(t)
    return render_template('mempool.html', txs=txs, format_time=format_time)

@app.route('/address/<address>', methods=['GET'])
def address_view(address):
    # validate address simple
    if not address.startswith('W') or len(address) < 6:
        abort(404)
    txs = find_address_txs(address)
    # compute balance
    balance_units = calculate_balance_from_chain(address)
    balance_wcn = format_wcn_units(balance_units)
    # prepare tx list with location
    tx_list = []
    for item in txs:
        tx = item['tx']
        blk = item['block']
        entry = dict(tx)
        entry['txid'] = tx_id(tx)
        if 'data' in entry and isinstance(entry['data'], dict):
            entry['to_display'] = entry['data'].get('to')
            entry['value_units'] = entry['data'].get('value')
            entry['fee_units'] = entry['data'].get('fee', None)
            entry['timestamp'] = entry['data'].get('timestamp')
        else:
            entry['to_display'] = entry.get('to')
            entry['value_units'] = entry.get('value', 0)
            entry['fee_units'] = entry.get('fee', None)
            entry['timestamp'] = entry.get('timestamp', None)
        entry['value_wcn'] = format_wcn_units(entry['value_units'])
        entry['fee_wcn'] = format_wcn_units(entry['fee_units']) if entry['fee_units'] is not None else None
        entry['block_index'] = blk.get('index') if blk else None
        tx_list.append(entry)

    return render_template('address.html', address=address, balance=balance_wcn, txs=tx_list, format_time=format_time)

@app.route('/supply', methods=['GET'])
def supply_view():
    chain = load_chain()
    total_units = sum(tx.get('value', 0) for block in chain for tx in block.get('transactions', []))
    return render_template('supply.html',
        max_supply=format_wcn_units(MAX_SUPPLY),
        circulating=format_wcn_units(total_units)
    )

# Simple 404 page for search misses
@app.errorhandler(404)
def not_found(e):
    return render_template('notfound.html', query=None), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
