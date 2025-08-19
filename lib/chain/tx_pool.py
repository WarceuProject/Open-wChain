# lib/chain/tx_pool.py
import json
import os
from app.config import DATA_DIR

#TX_POOL_FILE = 'data/tx_pool.json'
TX_POOL_FILE = os.path.join(DATA_DIR, "tx_pool.json")
def load_tx_pool():
    if not os.path.exists(TX_POOL_FILE):
        return []
    with open(TX_POOL_FILE, 'r') as f:
        return json.load(f)

def save_tx_pool(pool):
    with open(TX_POOL_FILE, 'w') as f:
        json.dump(pool, f, indent=2)

def add_transaction(tx):
    pool = load_tx_pool()
    pool.append(tx)
    save_tx_pool(pool)
