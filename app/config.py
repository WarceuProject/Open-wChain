#app/config.py
import os
DATA_DIR = os.environ.get("DATA_DIR", os.path.abspath("storage/data"))

BLOCKS_PATH = os.path.join(DATA_DIR, "blocks.json")
WALLETS_PATH = os.path.join(DATA_DIR, "wallets.json")
TX_POOL_PATH = os.path.join(DATA_DIR, "tx_pool.json")
PEERS_PATH = os.path.join(DATA_DIR, "peers.json")
# Fee rate per byte (satoshi)
FEE_RATE = 10