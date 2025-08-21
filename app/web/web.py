import os, sys, json, hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, abort
from decimal import Decimal, getcontext

# --- Setup Decimal presisi tinggi ---
getcontext().prec = 16
UNIT = 100_000_000  # 1 WCN = 100_000_000 units

# --- Allow importing project packages ---
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lib.chain.blockchain import load_chain, MAX_SUPPLY
from lib.chain.tx_pool import load_tx_pool
from lib.wallet.wallet import load_wallets

app = Flask(__name__, template_folder='templates', static_folder='static')


# --- UTILITIES ---
def tx_id(tx):
    s = json.dumps(tx, sort_keys=True).encode()
    return hashlib.sha256(s).hexdigest()

def format_time(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)


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
    pool = load_tx_pool()
    for tx in pool:
        frm = tx.get('from')
        to = tx.get('to') if 'to' in tx else (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else None)
        if frm == address or to == address:
            results.append({'tx': tx, 'block': None})
    return results

def sats_to_wcn(v):
    return (v or 0) / UNIT  # UNIT = 100_000_000

def format_wcn_units(v):
    return "{:,.8f}".format(sats_to_wcn(v or 0))


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



# --- ROUTES ---
@app.route('/', methods=['GET'])
def index():
    chain = load_chain()
    blocks = list(reversed(chain))
    summary = []
    total_txs = 0
    last_txs = []
    for b in blocks:
        txs = b.get('transactions', [])
        tx_count = len(txs)
        total_txs += tx_count
        reward_total = Decimal(0)
        for tx in txs:
            val = Decimal(tx.get('value', 0)) if 'value' in tx else (Decimal(tx.get('data', {}).get('value', 0)) if isinstance(tx.get('data'), dict) else Decimal(0))
            if tx.get('from') == 'COINBASE':
                reward_total += val
            last_txs.append({
                'txid': tx_id(tx),
                'time': format_time(tx.get('timestamp') or (tx.get('data', {}).get('timestamp') if isinstance(tx.get('data'), dict) else None)),
                'from': tx.get('from'),
                'to': (tx.get('to') if 'to' in tx else (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else None)),
                'amount_wcn': format_wcn_units(val),
                'fee_wcn': format_wcn_units(tx.get('fee', 0) if 'fee' in tx else (tx.get('data', {}).get('fee', 0) if isinstance(tx.get('data'), dict) else 0))
            })
        summary.append({
            'index': b.get('index'),
            'hash': b.get('hash'),
            'time': format_time(b.get('timestamp')),
            'tx_count': tx_count,
            'reward_units': reward_total,
            'reward_wcn': format_wcn_units(reward_total)
        })
    total_units = sum(
        (Decimal(tx.get('data', {}).get('value', 0)) + Decimal(tx.get('data', {}).get('fee', 0)))
        if isinstance(tx.get('data'), dict) else (Decimal(tx.get('value', 0)) + Decimal(tx.get('fee', 0)))
        for block in chain for tx in block.get('transactions', [])
    )
    mempool = load_tx_pool()
    return render_template('index.html',
        blocks=summary,
        total_blocks=len(chain),
        total_txs=total_txs,
        mempool_size=len(mempool),
        max_supply_wcn=format_wcn_units(MAX_SUPPLY),
        circulating_wcn=format_wcn_units(total_units),
        last_txs=last_txs[-10:]
    )

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
        t['value_units'] = Decimal(tx.get('value', 0)) if 'value' in tx else (Decimal(tx.get('data', {}).get('value', 0)) if isinstance(tx.get('data'), dict) else Decimal(0))
        t['fee_units'] = Decimal(tx.get('fee', 0))
        t['value_wcn'] = format_wcn_units(t['value_units'])
        t['fee_wcn'] = format_wcn_units(t['fee_units'])
        txs.append(t)
    reward_total = sum(
        Decimal(tx.get('value', 0)) + Decimal(tx.get('fee', 0)) 
        for tx in b.get('transactions', []) if tx.get('from') == 'COINBASE'
    )
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
    t['value_units'] = Decimal(tx.get('value', 0)) if 'value' in tx else (Decimal(tx.get('data', {}).get('value', 0)) if isinstance(tx.get('data'), dict) else Decimal(0))
    t['fee_units'] = Decimal(tx.get('fee', 0))
    t['value_wcn'] = format_wcn_units(t['value_units'])
    t['fee_wcn'] = format_wcn_units(t['fee_units'])
    return render_template('tx.html', tx=t, block=block, format_time=format_time)

@app.route('/address/<address>', methods=['GET'])
def address_view(address):
    if not address.startswith('W') or len(address) < 6:
        abort(404)

    txs = find_address_txs(address)
    balance_units = Decimal(calculate_balance_from_chain(address))
    balance_wcn = format_wcn_units(balance_units)

    tx_list = []
    for item in txs:
        tx = item['tx']
        blk = item['block']

        if isinstance(tx.get('data'), dict):
            value_units = Decimal(tx['data'].get('value', 0))
            to_addr = tx['data'].get('to')
        else:
            value_units = Decimal(tx.get('value', 0))
            to_addr = tx.get('to')

        fee_units = Decimal(tx.get('fee', 0))

        tx_list.append({
            'txid': tx_id(tx),
            'from_display': tx.get('from'),
            'to_display': to_addr,
            'value_units': value_units,
            'fee_units': fee_units,
            'value_wcn': format_wcn_units(value_units),
            'fee_wcn': format_wcn_units(fee_units),
            'block_index': blk.get('index') if blk else None
        })

    return render_template(
        'address.html',
        address=address,
        balance=balance_wcn,
        txs=tx_list,
        format_time=format_time
    )


@app.route('/mempool', methods=['GET'])
def mempool_view():
    pool = load_tx_pool()
    txs = []
    for tx in pool:
        t = dict(tx)
        t['txid'] = tx_id(tx)
        t['from_display'] = tx.get('from')
        t['to_display'] = (tx.get('data', {}).get('to') if isinstance(tx.get('data'), dict) else tx.get('to'))
        t['value_units'] = Decimal(tx.get('data', {}).get('value', 0) if isinstance(tx.get('data'), dict) else tx.get('value', 0))
        t['fee_units'] = Decimal(tx.get('fee', 0))
        t['value_wcn'] = format_wcn_units(t['value_units'])
        t['fee_wcn'] = format_wcn_units(t['fee_units'])
        txs.append(t)
    return render_template('mempool.html', txs=txs, format_time=format_time)

@app.route('/supply', methods=['GET'])
def supply_view():
    chain = load_chain()
    total_units = sum(
        (Decimal(tx.get('data', {}).get('value', 0)) + Decimal(tx.get('data', {}).get('fee', 0)))
        if isinstance(tx.get('data'), dict) else (Decimal(tx.get('value', 0)) + Decimal(tx.get('fee', 0)))
        for block in chain for tx in block.get('transactions', [])
    )
    return render_template('supply.html', circulating=format_wcn_units(total_units), max_supply=format_wcn_units(MAX_SUPPLY))

@app.route('/search', methods=['GET'])
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))

    chain = load_chain()
    wallets = load_wallets()

    # Block index
    if q.isdigit():
        index = int(q)
        if 0 <= index < len(chain):
            return redirect(url_for('block_view', index=index))
        else:
            return render_template('notfound.html', query=q), 404

    # Block hash
    for b in chain:
        if b.get('hash', '').startswith(q):
            return redirect(url_for('block_view', index=b.get('index')))

    # Transaction id
    for b in chain:
        for tx in b.get('transactions', []):
            if tx_id(tx).startswith(q):
                return redirect(url_for('tx_view', txid=tx_id(tx)))

    # Address valid
    if q.startswith('W') and any(w['address'] == q for w in wallets):
        return redirect(url_for('address_view', address=q))

    return render_template('notfound.html', query=q), 404

@app.errorhandler(404)
def not_found(e):
    return render_template('notfound.html', query=None), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
