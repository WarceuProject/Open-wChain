import os, sys, json, time, requests
import cmd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from wallet.wallet import generate_wallet, load_wallets, save_wallets, sign_transaction

RPC = 'http://localhost:8000/rpc'

class WalletCLI(cmd.Cmd):
    intro = "[openwchain-wallet] Type help or ? to list commands.\n"

    def __init__(self):
        super().__init__()
        self.wallets = load_wallets()
        self.default_wallet = self.wallets[0] if self.wallets else None
        self.update_prompt()

    def update_prompt(self):
        if self.default_wallet and self.default_wallet.get("alias"):
            self.prompt = f"[wallet-cli/{self.default_wallet['alias']}] > "
        else:
            self.prompt = "[wallet-cli] > "

    def save(self):
        save_wallets(self.wallets)

    def do_create(self, alias):
        "Create a new wallet: create <alias>"
        if not alias:
            print("Usage: create <alias>")
            return
        wallet = generate_wallet()
        wallet["alias"] = alias
        wallet["balance"] = 0
        self.wallets.append(wallet)
        self.default_wallet = wallet
        self.save()
        self.update_prompt()
        print("[✓] Wallet created and selected as default.")
        print(f"Alias: {alias}")
        print(f"Address: {wallet['address']}")

    def do_select(self, alias):
        "Select wallet as default: select <alias>"
        for w in self.wallets:
            if w.get("alias") == alias:
                self.default_wallet = w
                self.update_prompt()
                print(f"[✓] Selected wallet: {alias}")
                return
        print("[!] Wallet alias not found.")

    def do_list(self, arg):
        "List all wallets"
        for w in self.wallets:
            alias = w.get("alias", "N/A")
            print(f"- {alias}:{w['address']}:{w.get('balance', 0)}")

    def do_info(self, alias):
        "Show wallet info: info <alias>"
        for w in self.wallets:
            if w.get("alias") == alias:
                print(json.dumps(w, indent=2))
                return
        print("[!] Wallet not found.")

    def do_balance(self, address):
        "Check balance: balance <address>"
        if not address:
            print("Usage: balance <address>")
            return
        res = requests.post(RPC, json={
            "method": "wcn_getBalance",
            "params": [address]
        })
        print("Balance:", res.json().get('result'))

    def do_refresh(self, arg):
        "Refresh balances from blockchain"
        for w in self.wallets:
            res = requests.post(RPC, json={
                "method": "wcn_getBalance",
                "params": [w['address']]
            })
            w["balance"] = res.json().get("result", 0)
        self.save()
        print("[✓] Wallets updated.")

    def do_send(self, arg):
        "Send transaction: send <to_address> <amount>"
        if not self.default_wallet:
            print("[!] No default wallet selected.")
            return

        try:
            parts = arg.strip().split()
            if len(parts) != 2:
                raise ValueError
            to, value = parts[0], int(parts[1])
        except ValueError:
            print("Usage: send <to_address> <amount>")
            return

        # Check balance
        res = requests.post(RPC, json={
            "method": "wcn_getBalance",
            "params": [self.default_wallet['address']]
        })
        current_balance = res.json().get('result', 0)

        if value > current_balance:
            print(f"[!] Insufficient balance. You have {current_balance}, need {value}.")
            return

        tx_data = {
            "to": to,
            "value": value,
            "timestamp": int(time.time())
        }

        tx_str = json.dumps(tx_data, sort_keys=True)
        signature = sign_transaction(self.default_wallet['privateKey'], tx_str)

        full_tx = {
            "from": self.default_wallet['address'],
            "data": tx_data,
            "signature": signature,
            "publicKey": self.default_wallet['publicKey']
        }

        res = requests.post(RPC, json={
            "method": "wcn_sendTransaction",
            "params": [full_tx]
        })

        print(res.json())

    def do_mine(self, arg):
        "Mine a block using default wallet"
        if not self.default_wallet:
            print("[!] No default wallet selected.")
            return
        res = requests.post(RPC, json={
            "method": "wcn_mineBlock",
            "params": [self.default_wallet['address']]
        })
        print("[⛏️] Mined block:", res.json().get("result", {}).get("hash"))

    def do_exit(self, arg):
        "Exit"
        print("Goodbye!")
        return True

    def emptyline(self):
        pass

if __name__ == '__main__':
    WalletCLI().cmdloop()
