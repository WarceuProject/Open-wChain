# core/cli/wallet_cli.py
import os, sys
import json, time, requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from wallet.wallet import generate_wallet, load_wallets, save_wallets, sign_transaction

# Buat wallet baru
wallets = load_wallets()
wallet = generate_wallet()
wallets.append(wallet)
save_wallets(wallets)

print("Address :", wallet["address"])
print("Private :", wallet["privateKey"][:8] + "...")

# Kirim transaksi dari wallet yang baru dibuat
to_address = input("To: ")
value = int(input("Amount: "))

tx_data = {
    "to": to_address,
    "value": value,
    "timestamp": int(time.time())
}

# Stringify tx_data sebelum sign
tx_data_str = json.dumps(tx_data, sort_keys=True)
signature = sign_transaction(wallet['privateKey'], tx_data_str)

full_tx = {
    "from": wallet['address'],
    "data": tx_data,
    "signature": signature
}

res = requests.post('http://localhost:8000/rpc', json={
    "method": "wcn_sendTransaction",
    "params": [full_tx]
})
print(res.json())
