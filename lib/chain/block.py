import hashlib
import json
import time
from lib.consensus.difficulty import adjust_difficulty  # ambil fungsi difficulty

def hash_block(block):
    """Hash block menggunakan SHA256"""
    block_str = json.dumps({
        "index": block["index"],
        "previous_hash": block["previous_hash"],
        "timestamp": block["timestamp"],
        "transactions": block["transactions"],
        "nonce": block["nonce"],
        "difficulty": block.get("difficulty", 1)
    }, sort_keys=True).encode()
    return hashlib.sha256(block_str).hexdigest()

def create_block(index, previous_hash, transactions, blockchain):
    """
    Membuat block baru dengan proof-of-work (dynamic difficulty)
    blockchain: list block saat ini
    """
    difficulty = adjust_difficulty(blockchain)
    nonce = 0
    timestamp = int(time.time())

    while True:
        block = {
            "index": index,
            "previous_hash": previous_hash,
            "timestamp": timestamp,
            "transactions": transactions,
            "nonce": nonce,
            "difficulty": difficulty
        }
        h = hash_block(block)
        if h.startswith("0" * difficulty):
            block["hash"] = h
            return block
        nonce += 1
