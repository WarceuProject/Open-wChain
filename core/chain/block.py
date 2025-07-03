# openwchain/chain/block.py
import hashlib
import json
import time

def hash_block(block):
    block_str = json.dumps(block, sort_keys=True).encode()
    return hashlib.sha256(block_str).hexdigest()

def create_block(index, previous_hash, transactions, difficulty=4):
    nonce = 0
    timestamp = int(time.time())
    while True:
        block = {
            'index': index,
            'previous_hash': previous_hash,
            'timestamp': timestamp,
            'transactions': transactions,
            'nonce': nonce
        }
        h = hash_block(block)
        if h.startswith('0' * difficulty):
            block['hash'] = h
            return block
        nonce += 1
