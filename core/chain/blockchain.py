# core/chain/blockchain.py
import os, requests
import json, time
from .block import create_block
from chain.tx_pool import load_tx_pool, save_tx_pool
from wallet.wallet import verify_signature, load_wallets, save_wallets
from node.peers import load_peers

CHAIN_FILE = 'data/blocks.json'

def load_chain():
    if not os.path.exists(CHAIN_FILE):
        return []
    with open(CHAIN_FILE, 'r') as f:
        return json.load(f)

def save_chain(chain):
    os.makedirs(os.path.dirname(CHAIN_FILE), exist_ok=True)  
    with open(CHAIN_FILE, 'w') as f:
        json.dump(chain, f, indent=2)




def mine_block(miner_address, _):
    chain = load_chain()
    tx_pool = load_tx_pool()
    valid_txs = []

    wallets = load_wallets()
    address_map = {w['address']: w for w in wallets}

    for tx in tx_pool:
        sender = address_map.get(tx['from'])
        if sender and verify_signature(tx['data'], tx['signature'], sender['publicKey']):
            valid_txs.append(tx)
            sender['balance'] -= tx['data']['value']
            receiver = address_map.get(tx['data']['to'])
            if receiver:
                receiver['balance'] += tx['data']['value']

    reward_tx = {
        "from": "COINBASE",
        "to": miner_address,
        "value": 100000,
        "timestamp": int(time.time())
    }

    block = create_block(
        index=len(chain),
        previous_hash=chain[-1]['hash'] if chain else '0' * 64,
        transactions=valid_txs + [reward_tx]
    )

    chain.append(block)
    save_chain(chain)

    for peer in load_peers():
        try:
            requests.post(f'{peer}/sync', json=block, timeout=3)
        except:
            continue

    
    if miner_address in address_map:
        address_map[miner_address]['balance'] += 100000
    else:
        wallets.append({
            "address": miner_address,
            "privateKey": "",
            "publicKey": "",
            "balance": 100000
        })

    save_wallets(wallets)
    save_tx_pool([])

    return block

def update_wallets_from_chain(chain):
    wallets = load_wallets()
    address_map = {w['address']: w for w in wallets}

    for block in chain:
        for tx in block['transactions']:
            from_addr = tx.get("from")
            to_addr = tx.get("to")
            value = tx.get("value", 0)

            # auto-register wallet if belum ada
            if from_addr != "COINBASE" and from_addr not in address_map:
                address_map[from_addr] = {"address": from_addr, "balance": 0, "privateKey": "", "publicKey": ""}
            if to_addr not in address_map:
                address_map[to_addr] = {"address": to_addr, "balance": 0, "privateKey": "", "publicKey": ""}

            if from_addr != "COINBASE":
                address_map[from_addr]['balance'] -= value
            address_map[to_addr]['balance'] += value

    save_wallets(list(address_map.values()))
