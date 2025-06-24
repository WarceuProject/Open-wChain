import requests
import json

URL = "http://localhost:8000/blockchain"

def send_json_rpc(method, params=None, req_id=1):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": req_id
    }
    try:
        response = requests.post(URL, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def menu():
    print("\n=== WCN JSON-RPC CLI ===")
    print("1. wcn_chainId")
    print("2. wcn_blockNumber")
    print("3. wcn_getBalance")
    print("4. addWallets")
    print("5. addBalance")
    print("6. wcn_sendTransaction")
    print("7. wcn_getTransactionCount")
    print("8. info (lihat semua wallet)")
    print("9. net_version")
    print("10. wcn_gasPrice")
    print("11. wcn_estimateGas")
    print("0. Exit")

def main():
    while True:
        menu()
        choice = input("Pilih menu (0-11): ")

        if choice == "1":
            print(json.dumps(send_json_rpc("wcn_chainId"), indent=2))

        elif choice == "2":
            print(json.dumps(send_json_rpc("wcn_blockNumber"), indent=2))

        elif choice == "3":
            address = input("Masukkan address (Wa...): ")
            print(json.dumps(send_json_rpc("wcn_getBalance", [address]), indent=2))

        elif choice == "4":
            count = int(input("Jumlah wallet yang ingin ditambahkan: "))
            print(json.dumps(send_json_rpc("addWallets", [count]), indent=2))

        elif choice == "5":
            address = input("Masukkan address (Wa...): ")
            amount = input("Jumlah (dalam wei): ")
            print(json.dumps(send_json_rpc("addBalance", [address, amount]), indent=2))

        elif choice == "6":
            from_addr = input("Dari address (Wa...): ")
            to_addr = input("Ke address (Wa...): ")
            value = input("Jumlah transfer (dalam wei): ")
            tx = {
                "from": from_addr,
                "to": to_addr,
                "value": value
            }
            print(json.dumps(send_json_rpc("wcn_sendTransaction", [tx]), indent=2))

        elif choice == "7":
            address = input("Masukkan address (Wa...): ")
            print(json.dumps(send_json_rpc("wcn_getTransactionCount", [address]), indent=2))

        elif choice == "8":
            print(json.dumps(send_json_rpc("info"), indent=2))

        elif choice == "9":
            print(json.dumps(send_json_rpc("net_version"), indent=2))

        elif choice == "10":
            print(json.dumps(send_json_rpc("wcn_gasPrice"), indent=2))

        elif choice == "11":
            print(json.dumps(send_json_rpc("wcn_estimateGas"), indent=2))

        elif choice == "0":
            print("Keluar...")
            break

        else:
            print("Pilihan tidak valid.")

if __name__ == "__main__":
    main()
