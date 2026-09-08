# ⚡ Spesifikasi Optimasi API: Default Top 10 Data Terbaik & Pagination

Spesifikasi optimasi performa query database dan standarisasi batas data default `limit=10` pada seluruh endpoint list Polyfollow untuk mencegah latency tinggi, network timeout, dan error *"Failed to fetch"* di Swagger UI & Hermes Agent.

---

## 📋 1. Ringkasan Kebutuhan (Understanding Summary)
* **Masalah**: Database VPS saat ini melacak 1.157 wallet, 67.394 posisi, dan 1.081.428 transaksi. Endpoint `/api/v1/wallets` tanpa limit mencoba memproses seluruh 1.157 wallet dalam satu payload raksasa sehingga memakan waktu > 15–20 detik dan memicu browser timeout (*Failed to fetch*).
* **Solusi**: Menerapkan standardisasi default **Top 10 Data Terbaik** (`limit: int = 10`) pada level database SQL di seluruh endpoint list.
* **Target Pengguna**: Hermes AI Agent dan operator Swagger UI.
* **Kriteria Keberhasilan**: Waktu respon API turun menjadi $< 50$ milidetik tanpa merusak skema data JSON yang sudah ada (*backward-compatible*).

---

## ⚙️ 2. Matriks Perubahan Endpoint

| Endpoint | Default Limit Lama | Default Limit Baru | Logika Pengurutan "Terbaik" |
| :--- | :--- | :--- | :--- |
| **`GET /api/v1/wallets`** | Tidak ada (Semua 1.157 wallet) | **`10`** (dengan pagination `offset=0`) | `Snapshot.total_volume_usdc.desc()` (Volume terbesar) |
| **`GET /api/v1/signals/consensus`** | `20` | **`10`** | `confidence_score.desc()`, volume terbesar |
| **`GET /api/v1/signals/holdings`** | `30` | **`10`** | `total_whales_count.desc()`, nilai portofolio terbesar |
| **`GET /api/v1/signals/exits`** | `20` | **`10`** | `total_exit_volume_usdc.desc()` (Dump terbesar teratas) |
| **`GET /api/v1/trades/recent`** | `50` | **`10`** | `traded_at.desc()` (Transaksi whale paling baru) |
| **`GET /api/v1/positions`** | `50` | **`10`** | `cur_value.desc()` (Posisi exposure nilai terbesar) |

---

## 🧠 3. Desain Teknis Query SQL (`GET /api/v1/wallets`)

```python
query = (
    select(Wallet, Snapshot)
    .outerjoin(Snapshot, Wallet.address == Snapshot.wallet_address)
    .order_by(func.coalesce(Snapshot.total_volume_usdc, 0.0).desc())
    .limit(limit)
    .offset(offset)
)
```
* Menghilangkan proses batch querying 1.157 wallet menjadi hanya tepat 10 baris di memori database.
* Kunci in-memory cache: `f"wallets:list:{active_only}:{limit}:{offset}"`.

---

## 📝 4. Riwayat Keputusan Desain (Decision Log)
* **D-01**: Mengubah nilai default parameter `limit` di seluruh endpoint list menjadi `10`.
* **D-02**: Menambahkan parameter pagination `limit` dan `offset` pada `GET /api/v1/wallets`.
* **D-03**: Mengurutkan `GET /api/v1/wallets` berdasarkan akumulasi volume bandar terbesar (`Snapshot.total_volume_usdc.desc()`).
* **D-04**: Mengurutkan `GET /api/v1/positions` berdasarkan nilai portofolio terbesar (`Position.cur_value.desc()`).
