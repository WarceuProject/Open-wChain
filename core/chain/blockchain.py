# openwchain/chain/blockchain.py
import os
import json, time
from .block import create_block

CHAIN_FILE = 'data/blocks.json'

def load_chain():
    if not os.path.exists(CHAIN_FILE):
        return []
    with open(CHAIN_FILE, 'r') as f:
        return json.load(f)

def save_chain(chain):
    with open(CHAIN_FILE, 'w') as f:
        json.dump(chain, f, indent=2)

def mine_block(miner_address, tx_pool):
    chain = load_chain()
    previous_hash = chain[-1]['hash'] if chain else '0' * 64
    index = len(chain)
    reward_tx = {
        "from": "COINBASE",
        "to": miner_address,
        "value": 100000,
        "timestamp": int(time.time())
    }
    block = create_block(index, previous_hash, tx_pool + [reward_tx])
    chain.append(block)
    save_chain(chain)
    return block
