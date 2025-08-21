# lib/consensus/config.py

# Nama Jaringan
NETWORK_NAME = "Open wChain Network"
SYMBOL = "WCN"

# target block sec = 10 min
BLOCK_TIME = 600  

# Max Supply
MAX_SUPPLY = 20_000_000  # 20 juta WCN

# Reward Awal per Block
INITIAL_BLOCK_REWARD = 50.0  # WCN

# Halving Interval  210,000 block halving
HALVING_INTERVAL = 210_000  

# Initial difficulty
INITIAL_DIFFICULTY = 1

# Difficulty Adjustment Interval (jumlah block)
DIFFICULTY_ADJUSTMENT_INTERVAL = 2016  

# Panjang Blockchain Target dalam byte (opsional, buat prune)
MAX_BLOCKCHAIN_SIZE_MB = 5000  

# Genesis Block
GENESIS_BLOCK = {
    "version": 1,
    "previous_hash": "0" * 64,
    "merkle_root": None,  # akan di-generate saat create genesis
    "timestamp": 1730000000,
    "difficulty": 1,
    "nonce": 0,
    "transactions": [],
}

# Fungsi untuk hitung reward
def get_block_reward(height: int) -> float:
    halvings = height // HALVING_INTERVAL
    reward = INITIAL_BLOCK_REWARD / (2 ** halvings)
    return max(reward, 0)


if __name__ == "__main__":
    # Contoh cek reward di block tertentu
    for h in [0, 210_000, 420_000, 630_000]:
        print(f"Block {h} reward: {get_block_reward(h)} WCN")
