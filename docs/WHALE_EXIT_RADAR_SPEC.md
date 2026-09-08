# 🚨 Spesifikasi Desain: Whale Exit & Dump Radar API (`GET /api/v1/signals/exits`)

Spesifikasi resmi endpoint deteksi penjualan, profit-taking, dan dumping bandar Polymarket untuk proteksi risiko dan pemicu Take-Profit / Stop-Loss terotomatisasi oleh **Hermes AI Agent**.

---

## 📋 1. Ringkasan Kebutuhan & Konteks (Understanding Summary)
* **Tujuan**: Menyediakan sinyal peringatan dini saat bandar yang sedang dilacak mulai melepas (`SELL`), mengambil untung (*profit taking*), atau membuang posisi (*panic dump*).
* **Target Pengguna**: Hermes AI Agent untuk memicu order keluar pasar (`EMERGENCY_CLOSE` atau `TRIM_50%`).
* **Pendekatan**: Hybrid Real-Time — Mengagregasi transaksi `SELL` di tabel `trades` dalam rentang waktu (`timeframe`) dan memvalidasi sisa saldo share di tabel `positions`.

---

## ⚙️ 2. Spesifikasi Endpoint

* **Method & Path**: `GET /api/v1/signals/exits`
* **Tags**: `Smart Signals & Consensus`
* **Query Parameters**:
  * `timeframe` (str, default `"24h"`): Rentang waktu agregasi (`1h`, `6h`, `24h`).
  * `min_exit_usd` (float, default `1000.0`): Minimal akumulasi volume penjualan per market.
  * `min_whales` (int, default `1`): Minimal jumlah bandar yang melakukan penjualan.
  * `limit` (int, default `20`): Batas jumlah sinyal exit yang dikembalikan.

### Struktur Skema Response (Pydantic Model)
```json
[
  {
    "condition_id": "0x1234abcd5678ef90...",
    "market_title": "Will Donald Trump create a Bitcoin strategic reserve?",
    "market_slug": "will-donald-trump-create-a-bitcoin-strategic-reserve",
    "outcome_exited": "YES",
    "timeframe": "24h",
    "exiting_whales_count": 2,
    "total_exit_volume_usdc": 34500.0,
    "average_exit_price": 0.72,
    "exit_type": "WHALE_EXODUS",
    "urgency": "CRITICAL",
    "recommended_action": "EMERGENCY_CLOSE",
    "is_full_exit": true,
    "exiting_whales": [
      {
        "address": "0xabc123...",
        "label": "Whale Alpha",
        "sold_volume_usdc": 20000.0,
        "sold_shares": 27777.7,
        "average_exit_price": 0.72,
        "remaining_shares": 0.0,
        "is_position_cleared": true,
        "archetype": "INSIDER_SPECIALIST"
      }
    ],
    "ai_rationale": "CRITICAL ALERT: 2 Tier-1 whales dumped $34.5k YES shares within 24h and cleared 100% of their positions. Immediate exit recommended."
  }
]
```

---

## 🧠 3. Logika Klasifikasi & Urgensi

| Kondisi Data Transaksi & Posisi | Tipe Exit (`exit_type`) | Tingkat Urgensi (`urgency`) | Aksi Rekomendasi Hermes (`recommended_action`) |
| :--- | :--- | :--- | :--- |
| $\ge 2$ bandar menjual di market yang sama **ATAU** 1 bandar besar dump $> \$20,000$ dan sisa share = 0 | `WHALE_EXODUS` | `CRITICAL` | **`EMERGENCY_CLOSE`** (Tutup posisi 100% instan) |
| Bandar menjual porsi signifikan ($> 50\%$) pada harga tinggi ($> \$0.75$) namun masih menyisakan share | `PROFIT_TAKING` | `HIGH` | **`TRIM_50%`** (Amankan modal dan kunci separuh profit) |
| Bandar menjual rugi pada harga jatuh ($< \$0.30$) | `STOP_LOSS_DUMP` | `HIGH` | **`EMERGENCY_CLOSE`** (Ikut cut loss sebelum likuiditas habis) |
| Penjualan bernilai kecil / rebalancing portofolio | `PARTIAL_TRIM` | `MEDIUM` | **`TIGHTEN_STOP`** (Kawal ketat trailing stop) |

---

## 📝 4. Riwayat Keputusan Desain (Decision Log)
* **D-01**: Menetapkan endpoint resmi `GET /api/v1/signals/exits` sebagai pendamping endpoint akumulasi `GET /api/v1/signals/consensus`.
* **D-02**: Memilih pendekatan Hybrid Real-Time: Query transaksi `SELL` di tabel `trades` digabungkan dengan sisa saldo kepemilikan di tabel `positions`.
* **D-03**: Menghasilkan instruksi terstruktur untuk Hermes AI Agent (`EMERGENCY_CLOSE`, `TRIM_50%`, `TIGHTEN_STOP`) dan teks deskriptif `ai_rationale`.

---

## 🧪 5. Rencana Verifikasi & Testing
1. **Unit Test Single Whale Partial Exit**: Validasi output `exit_type: PROFIT_TAKING`, `urgency: HIGH`, `recommended_action: TRIM_50%`.
2. **Unit Test Multi-Whale Full Exit**: Validasi output `exit_type: WHALE_EXODUS`, `urgency: CRITICAL`, `recommended_action: EMERGENCY_CLOSE`.
3. **Filtering Test**: Validasi parameter `min_exit_usd`, `min_whales`, dan `timeframe`.
