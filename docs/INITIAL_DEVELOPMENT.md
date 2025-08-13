# Initial Development - Open wChain Network (OwCN)

## Status Pengembangan

**Q1: Experimental (DEV) — On Going**

OwCN saat ini berada pada fase awal pengembangan (experimental). Tujuan fase ini adalah membangun fondasi blockchain yang modular, ringan, dan dapat diuji oleh developer dan peneliti.

---

## Milestone & Tugas Sedang Berjalan

1. **Implementasi Fitur Dasar Blockchain**

   * Struktur blok dan blockchain
   * Penyimpanan transaksi
   * Validasi blok

2. **Pengujian dan Validasi JSON-RPC**

   * Endpoint dasar untuk node
   * Integrasi dengan CLI dan wallet

3. **Penyempurnaan Arsitektur Modular**

   * Memisahkan modul `chain`, `wallet`, dan `node`
   * Membuat namespace yang rapi (`lib/chain`, `lib/node`, `lib/wallet`)

4. **Dokumentasi dan Contoh Penggunaan**

   * README.md dan README-en.md diperbarui
   * Contoh CLI & API sederhana

5. **Pengembangan Komunitas & Kontribusi Terbuka**

   * Guidelines kontribusi
   * Pengaturan branch `python-core-v1`

6. **Penyebaran & Pengujian di Lingkungan Tesnet**

   * Backup data awal di `lib/data.bak` dan `storage/data`
   * Testing node dan CLI

7. **Evaluasi Risiko Keamanan**

   * Review alur transaksi
   * Penanganan double spending dan integritas blok

8. **Integrasi Multi Bahasa Pemrograman**

   * Memastikan JSON-RPC dapat diakses dari Python dan klien lain

9. **Rencana Pengembangan Selanjutnya**

   * Persiapan milestone Q2 (Beta / Testnet)
   * Penyempurnaan konsensus
   * API publik untuk developer

---

## Catatan Teknis

* Semua kode modular diletakkan di `lib/`
* CLI terpisah di `app/cli`
* API terpisah di `app/api`
* Data JSON berada di `storage/data` untuk memudahkan backup dan testing
* Struktur baru akan dijadikan standar untuk branch `python-core-v1`

---

## Menjalankan Node Developer & Debugging

### 1. Jalankan Node (Start)

Pastikan berada di root proyek (`python-core-v1`) lalu jalankan:

```bash
python3 -m app.cli.node start
```

* `start` memulai node developer.

### 2. Hentikan Node (Stop)

Jika modul node mendukung perintah `stop`:

```bash
python3 -m app.cli.node stop
```

### 3. Pantau Log / Debug

Jika node menulis log ke file, misal `debug.log`:

```bash
tail -f storage/data/debug.log
```

* `-f` mengikuti log secara real-time. Gunakan `Ctrl+C` untuk berhenti.

### Tips Tambahan

* Jalankan node di background:

```bash
python3 -m app.cli.node start &
```

atau

```bash
nohup python3 -m app.cli.node start > storage/data/debug.log 2>&1 &
```

* Pastikan semua dependency sudah diinstal:

```bash
pip install -r requirements.txt
```

---

## Testing Node via cURL (HTTP Methods)

Node OwCN menyediakan beberapa endpoint untuk diuji menggunakan `curl`.

### 1. Test Node Running

* **Endpoint:** `/`
* **Method:** GET

```bash
curl http://localhost:8000/
```

Expected output:

```json
{"status": "running"}
```

### 2. Full Chain

* **Endpoint:** `/fullchain`
* **Method:** GET

```bash
curl http://localhost:8000/fullchain
```

### 3. RPC Endpoint

* **Endpoint:** `/rpc`
* **Method:** POST
* **Content-Type:** application/json

#### a. Dapatkan jumlah blok

```bash
curl -X POST http://localhost:8000/rpc \
-H "Content-Type: application/json" \
-d '{"method": "wcn_blockNumber", "params": []}'
```

#### b. Mine block

```bash
curl -X POST http://localhost:8000/rpc \
-H "Content-Type: application/json" \
-d '{"method": "wcn_mineBlock", "params": ["miner_address"]}'
```

#### c. Cek saldo

```bash
curl -X POST http://localhost:8000/rpc \
-H "Content-Type: application/json" \
-d '{"method": "wcn_getBalance", "params": ["wallet_address"]}'
```

#### d. Kirim transaksi

```bash
curl -X POST http://localhost:8000/rpc \
-H "Content-Type: application/json" \
-d '{
    "method": "wcn_sendTransaction",
    "params": [{
        "from": "sender_address",
        "publicKey": "sender_public_key",
        "signature": "signed_data",
        "data": {"to": "receiver_address", "value": 10}
    }]
}'
```

### 4. Peer Management

#### a. Tambah peer

* **Endpoint:** `/add_peer`
* **Method:** POST

```bash
curl -X POST http://localhost:8000/add_peer \
-H "Content-Type: application/json" \
-d '{"url": "http://peer_ip:8000"}'
```

#### b. Lihat peer list

* **Endpoint:** `/peers`
* **Method:** GET

```bash
curl http://localhost:8000/peers
```

### 5. Chain & Sync

#### a. Ambil chain saat ini

* **Endpoint:** `/chain`
* **Method:** GET

```bash
curl http://localhost:8000/chain
```

#### b. Sync block dari peer

* **Endpoint:** `/sync`
* **Method:** POST

```bash
curl -X POST http://localhost:8000/sync \
-H "Content-Type: application/json" \
-d '{"index": 5, "hash": "block_hash", "transactions": []}'
```

### Catatan

* Gunakan `Content-Type: application/json` untuk semua POST request.
* Endpoint dapat bertambah atau berubah seiring pengembangan node.
* Gunakan `jq` untuk parsing JSON:

```bash
curl http://localhost:8000/fullchain | jq
```

---

## Wallet CLI - Penggunaan & Contoh

Jalankan wallet CLI:

```bash
python3 -m app.cli.wallet_cli
```

Prompt akan muncul:

```
[openwchain-wallet] Type help or ? to list commands.
[wallet-cli/dev] >
```

### 1. Melihat Perintah Tersedia

```
help
```

Output:

```
Documented commands (type help <topic>):
========================================
balance  create  exit  help  info  list  mine  refresh  select  send
```

### 2. Membuat Wallet Baru

```
create mywallet
```

Output:

```
[✓] Wallet created and selected as default.
Alias: mywallet
Address: WCN123abc...
```

### 3. Melihat Daftar Wallet

```
list
```

Output:

```
* mywallet:WCN123abc...:0.00000000 WCN
```

### 4. Memilih Wallet Default

```
select mywallet
```

Output:

```
[✓] Selected wallet: mywallet
```

### 5. Melihat Informasi Wallet

```
info mywallet
```

Output (JSON terformat):

```json
{
  "alias": "mywallet",
  "address": "WCN123abc...",
  "publicKey": "pubkey_here",
  "privateKey": "privkey_here",
  "balance": "0.00000000 WCN"
}
```

### 6. Mengecek Saldo Wallet

```
balance WCN123abc...
```

Output:

```
Balance: 0.00000000 WCN
```

### 7. Refresh Semua Saldo Wallet

```
refresh
```

Output:

```
[✓] Wallets updated.
```

### 8. Mengirim Transaksi

```
send WCN456def... 1.25
```

Output jika berhasil:

```
{'result': 'Transaction added to pool'}
```

Jika saldo tidak cukup:

```
[!] Insufficient balance. You have 0.50000000 WCN, need 1.25000000 WCN.
```

### 9. Menambang Blok

```
mine
```

Output:

```
[⛏️] Mined block: 000abc123def...
```

### 10. Keluar dari Wallet CLI

```
exit
```

Output:

```
Goodbye!
```

### Catatan

* Wallet CLI **dapat berubah** seiring pengembangan.
* Pastikan node sedang berjalan sebelum menggunakan Wallet CLI agar transaksi dan saldo dapat di-refresh.
