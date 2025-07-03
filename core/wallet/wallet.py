# core/wallet/wallet.py
import ecdsa
import os
import hashlib
import json
# config DB
WALLET_DB = 'data/wallets.json'
# wallet init
def generate_wallet():
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    priv = sk.to_string().hex()
    pub = vk.to_string().hex()
    address = 'W' + hashlib.sha256(vk.to_string()).hexdigest()[:40]
    return {
        "address": address,
        "privateKey": priv,
        "publicKey": pub,
        "balance": 0
    }

def load_wallets():
    if not os.path.exists(WALLET_DB):
        return []
    with open(WALLET_DB, 'r') as f:
        return json.load(f)

def save_wallets(wallets):
    with open(WALLET_DB, 'w') as f:
        json.dump(wallets, f, indent=2)

# signature
def sign_trasaction(tx, private_key_hex):
    sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hex), curve=ecdsa.SECP256k1)
    tx_str = json.dumps(tx, sort_keys=True).encode()
    signature = sk.sign(tx_str)
    return signature.hex()

def verify_signature(tx, signature_hex, public_key_hex):
    vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(public_key_hex),curve=ecdsa.SECP256k1)
    tx_str = json.dumps(tx, sort_keys=True).encode()
    try:
        return vk.verify(bytes.fromhex(signature_hex), tx_str)
    except ecdsa.BadSignatureError:
        return False
    