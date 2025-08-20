import os, requests, hashlib, json, time
from .block import create_block
#from chain.tx_pool import load_tx_pool, save_tx_pool
#from wallet.wallet import verify_signature, load_wallets, save_wallets
from lib.wallet.wallet import verify_signature, load_wallets, save_wallets
#from node.peers import load_peers
from lib.node.peers import load_peers
from app.config import DATA_DIR
from .tx_pool import load_tx_pool, save_tx_pool


CHAIN_FILE = os.path.join(DATA_DIR, "blocks.json")
MAX_SUPPLY = 20_000_000 * 100_000_000  # Max Supply dalam satoshis

def load_chain():
    if not os.path.exists(CHAIN_FILE):
        return []
    with open(CHAIN_FILE, 'r') as f:
        return json.load(f)

def save_chain(chain):
    os.makedirs(os.path.dirname(CHAIN_FILE), exist_ok=True)
    with open(CHAIN_FILE, 'w') as f:
        json.dump(chain, f, indent=2)

def get_total_supply(chain):
    total = 0
    for block in chain:
        for tx in block['transactions']:
            total += tx.get('value', 0)
    return total

# ============================
def mine_block(miner_addresses, _, reward_value=None):
    """
    miner_addresses: list miner
    reward_value: opsional, jika None → dihitung otomatis
    """
    chain = load_chain()
    tx_pool = load_tx_pool()
    valid_txs = []

    wallets = load_wallets()
    address_map = {w['address']: w for w in wallets}

    # Validasi transaksi
    for tx in tx_pool:
        sender = address_map.get(tx['from'])
        if sender and verify_signature(tx['data'], tx['signature'], sender['publicKey']):
            valid_txs.append(tx)
            sender['balance'] -= tx['data']['value']
            receiver = address_map.get(tx['data']['to'])
            if receiver:
                receiver['balance'] += tx['data']['value']

    # Hitung reward otomatis jika None
    total_supply = get_total_supply(chain)
    tx_fee_total = sum([tx.get('fee', 0) for tx in tx_pool])

    HALVING_INTERVAL = 210_000  # Halving block
    INITIAL_REWARD = 50 * 100_000_000  # 50 WCN

    if reward_value is None:
        if total_supply < MAX_SUPPLY:
            current_reward = INITIAL_REWARD // (2 ** (len(chain) // HALVING_INTERVAL))
            reward_value = min(MAX_SUPPLY - total_supply, current_reward) + tx_fee_total
        else:
            reward_value = tx_fee_total

    # Pembagian reward per miner
    per_miner_reward = reward_value // len(miner_addresses) if miner_addresses else reward_value

    reward_txs = []
    for addr in miner_addresses:
        reward_txs.append({
            "from": "COINBASE",
            "to": addr,
            "value": per_miner_reward,
            "timestamp": int(time.time())
        })
        if addr in address_map:
            address_map[addr]['balance'] += per_miner_reward
        else:
            wallets.append({
                "address": addr,
                "privateKey": "",
                "publicKey": "",
                "balance": per_miner_reward,
                "isLocal": True
            })

    # Buat block baru
    block = create_block(
        index=len(chain),
        previous_hash=chain[-1]['hash'] if chain else '0'*64,
        transactions=valid_txs + reward_txs
    )

    chain.append(block)
    save_chain(chain)

    # Broadcast ke peers
    for peer in load_peers():
        try:
            requests.post(f'{peer}/sync', json=block, timeout=3)
        except:
            continue

    save_wallets(wallets)
    save_tx_pool([])

    return block

# ============================
def update_wallets_from_chain(chain):
    wallets = load_wallets()
    address_map = {w['address']: w for w in wallets}

    for w in wallets:
        w['balance'] = 0

    for block in chain:
        for tx in block['transactions']:
            sender_addr = tx.get('from')
            to_addr = tx['data']['to'] if 'data' in tx else tx.get('to')
            value = tx['data']['value'] if 'data' in tx else tx.get('value')

            if sender_addr != "COINBASE" and sender_addr in address_map:
                address_map[sender_addr]['balance'] -= value
            if to_addr in address_map:
                address_map[to_addr]['balance'] += value
            else:
                address_map[to_addr] = {
                    "address": to_addr,
                    "privateKey": "",
                    "publicKey": "",
                    "balance": value,
                    "isLocal": False
                }
                wallets.append(address_map[to_addr])

    save_wallets(wallets)

# ============================
def hash_block(block):
    block_data = {
        "index": block["index"],
        "previous_hash": block["previous_hash"],
        "timestamp": block["timestamp"],
        "transactions": block["transactions"],
        "nonce": block["nonce"]
    }
    block_str = json.dumps(block_data, sort_keys=True)
    return hashlib.sha256(block_str.encode()).hexdigest()

def is_block_valid(block, previous_block, wallets):
    if block["hash"] != hash_block(block):
        print("[!] Invalid block hash.")
        return False
    if not block["hash"].startswith("0000"):
        print("[!] Hash doesn't meet difficulty requirement.")
        return False
    if block["previous_hash"] != previous_block["hash"]:
        print("[!] Previous hash mismatch.")
        return False

    address_map = {w["address"]: dict(w) for w in wallets}
    for tx in block["transactions"]:
        if tx["from"] == "COINBASE":
            continue
        if not verify_signature(tx['data'], tx['signature'], tx['publicKey']):
            print("[!] Invalid signature.")
            return False
        sender = address_map.get(tx['from'])
        if not sender or sender['balance'] < tx['data']['value']:
            print("[!] Insufficient balance.")
            return False
        sender["balance"] -= tx['data']['value']
        receiver = address_map.get(tx['data']['to'])
        if receiver:
            receiver['balance'] += tx['data']['value']
        else:
            address_map[tx['data']['to']] = {
                "address": tx['data']['to'],
                "balance": tx['data']['value'],
                "privateKey": "",
                "publicKey": ""
            }
    return True
