import requests
import json
from decimal import Decimal, getcontext

getcontext().prec = 50
URL = "http://localhost:8000/blockchain"

def send_rpc(method, params=None, req_id=1):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": req_id
    }
    try:
        response = requests.post(URL, json=payload)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def hex_to_wcn(hex_value):
    try:
        if hex_value.startswith("Wb"):
            wei = int(hex_value[2:], 16)
        elif hex_value.startswith("0x"):
            wei = int(hex_value, 16)
        else:
            return hex_value
        wcn = Decimal(wei) / Decimal(1e18)
        return f"{wcn:.6f} WCN ({wei} wei)"
    except:
        return hex_value

def help_menu():
    print("""
Perintah CLI yang tersedia:
- info                              : Menampilkan semua wallet dan saldo (format manusiawi)
- balance <address>                : Menampilkan saldo wallet tertentu
- send <from> <to> <amount_in_wei> : Kirim WCN (dalam wei)
- mine                             : Tambah blok baru (simulasi PoW)
- block                            : Lihat blok terakhir
- exit / quit                      : Keluar dari CLI
""")

def info():
    res = send_rpc("info")
    result = res.get("result", [])
    if not result:
        print("⚠️  Tidak ada wallet.")
        return
    print("📒 === Daftar Wallet ===")
    for wallet in result:
        print(f"Address: {wallet['address']}")
        print(f"Balance: {hex_to_wcn(wallet['balance'])}")
        print("-" * 30)

def balance(address):
    res = send_rpc("wcn_getBalance", [address])
    if "result" in res:
        print(f"💰 Saldo {address}: {hex_to_wcn(res['result'])}")
    else:
        print(f"❌ Gagal mengambil saldo. Error: {res.get('error')}")

def send(from_addr, to_addr, amount):
    try:
        amount = str(int(amount))  # pastikan integer
    except:
        print("❌ Amount harus berupa angka (wei).")
        return
    tx = {
        "from": from_addr,
        "to": to_addr,
        "value": amount
    }
    res = send_rpc("wcn_sendTransaction", [tx])
    if "result" in res:
        print(f"✅ Transaksi berhasil: {res['result']}")
    else:
        print(f"❌ Gagal kirim: {res.get('error')}")

def mine():
    res = send_rpc("wcn_mineBlock")
    print(json.dumps(res, indent=2))

def show_last_block():
    res = send_rpc("wcn_getBlockByNumber", ["0x1"])  # sementara blok tetap dummy 0x1
    print(json.dumps(res, indent=2))

def repl():
    print("💻 Selamat datang di wChain Wallet CLI")
    print("Ketik 'help' untuk melihat perintah.")
    while True:
        try:
            cmd = input("wChain > ").strip()
            if not cmd:
                continue
            parts = cmd.split()
            command = parts[0].lower()

            if command in ["exit", "quit"]:
                print("👋 Keluar dari wallet...")
                break
            elif command == "help":
                help_menu()
            elif command == "info":
                info()
            elif command == "balance":
                if len(parts) < 2:
                    print("Usage: balance <address>")
                else:
                    balance(parts[1])
            elif command == "send":
                if len(parts) != 4:
                    print("Usage: send <from> <to> <amount>")
                else:
                    send(parts[1], parts[2], parts[3])
            elif command == "mine":
                mine()
            elif command == "block":
                show_last_block()
            else:
                print("❓ Perintah tidak dikenal. Ketik 'help'.")
        except KeyboardInterrupt:
            print("\n👋 Keluar...")
            break
        except Exception as e:
            print(f"⚠️  Error: {e}")

if __name__ == "__main__":
    repl()
