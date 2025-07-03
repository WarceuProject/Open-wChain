# core/cli/wcli.py
import os, sys, json, time, requests
import cmd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from wallet.wallet import generate_wallet, load_wallets, save_wallets, sign_transaction

RPC = 'http://localhost:8000/rpc'

class WalletCLI(cmd.Cmd):
    intro = "[openwchain-wallet] Type help or ? to list commands.\n"
    prompt = "[wallet-cli] > "

    def do_create(self, arg):
        "Create a new wallet"
        wallets = load_wallets()
        wallet = generate_wallet()
        wallets.append(wallet)
        save_wallets(wallets)
        print("[✓] New wallet created:")
        print("Address:", wallet['address'])
        print("Private:", wallet['privateKey'][:8] + "...")

    def do_list(self, arg):
        "List all wallets"
        for w in load_wallets():
            print("-", w['address'])

    def do_balance(self, arg):
        "Check balance: balance <address>"
        if not arg:
            print("Usage: balance <address>")
            return
        res = requests.post(RPC, json={
            "method": "wcn_getBalance",
            "params": [arg]
        })
        print("Balance:", res.json().get('result'))

    def do_info(self, arg):
        "Show wallet info: info <address>"
        for w in load_wallets():
            if w['address'] == arg:
                print(json.dumps(w, indent=2))
                return
        print("[!] Wallet not found.")

    def do_send(self, arg):
        "Send transaction from default wallet"
        wallets = load_wallets()
        sender = wallets[0]
        to = input("To address: ")
        value = int(input("Amount: "))

        tx_data = {
            "to": to,
            "value": value,
            "timestamp": int(time.time())
        }
        tx_str = json.dumps(tx_data, sort_keys=True)
        signature = sign_transaction(sender['privateKey'], tx_str)

        full_tx = {
            "from": sender['address'],
            "data": tx_data,
            "signature": signature
        }

        res = requests.post(RPC, json={
            "method": "wcn_sendTransaction",
            "params": [full_tx]
        })
        print(res.json())

    def do_mine(self, arg):
        "Mine a block using the default wallet"
        wallets = load_wallets()
        miner = wallets[0]['address']
        res = requests.post(RPC, json={
            "method": "wcn_mineBlock",
            "params": [miner]
        })
        print("[⛏️] Mined block:", res.json().get("result", {}).get("hash"))

    def do_exit(self, arg):
        "Exit the wallet shell"
        print("Goodbye!")
        return True

    def emptyline(self):
        pass

if __name__ == '__main__':
    WalletCLI().cmdloop()
