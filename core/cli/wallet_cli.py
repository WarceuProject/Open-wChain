# openwchain/cli/wallet_cli.py
from wallet.wallet import generate_wallet, load_wallets, save_wallets, sign_transaction
import requests, time

wallets = load_wallets()
wallet = generate_wallet()
wallets.append(wallet)
save_wallets(wallets)

print("Address :", wallet["address"])
print("Private :", wallet["privateKey"][:8] + "...")

sender = load_wallets()[0]
to_address = input("To: ")
value = int(input("Amount: "))

tx_data = {
    "to": to_address,
    "value": value,
    "timestamp": int(time.time())
}
signature = sign_transaction(tx_data, sender['privateKey'])

full_tx = {
    "from": sender['address'],
    "data": tx_data,
    "signature": signature
}

res = requests.post('http://localhost:8000/rpc', json={
    "method": "wcn_sendTransaction",
    "params": [full_tx]
})
print(res.json())
