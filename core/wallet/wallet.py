# core/wallet/wallet.py
import ecdsa
import os
import hashlib
import json

WALLET_DB = 'data/wallets.json'

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
        "balance": 0,
        "isLocal": True
    }

def load_wallets():
    if not os.path.exists(WALLET_DB):
        return []
    with open(WALLET_DB, 'r') as f:
        return json.load(f)

def save_wallets(wallets):
    os.makedirs(os.path.dirname(WALLET_DB), exist_ok=True)
    with open(WALLET_DB, 'w') as f:
        json.dump(wallets, f, indent=2)

def sign_transaction(private_key_hex, tx_str):
    try:
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(private_key_hex), curve=ecdsa.SECP256k1)
    except Exception:
        raise Exception("[!] Private key invalid. Must be hex.")

    signature = sk.sign(tx_str.encode())
    return signature.hex()

def verify_signature(tx, signature_hex, public_key_hex):
    vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=ecdsa.SECP256k1)
    tx_str = json.dumps(tx, sort_keys=True).encode()
    try:
        return vk.verify(bytes.fromhex(signature_hex), tx_str)
    except ecdsa.BadSignatureError:
        return False
