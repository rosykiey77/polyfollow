# 📡 Panduan Live Dokumentasi API & Integrasi Hermes Agent

Dokumentasi resmi untuk mengakses, mengonfigurasi, dan mengonsumsi API Polyfollow (Polymarket Bandar Tracker) oleh Hermes AI Agent.

---

## 🔗 1. Tautan Live Dokumentasi (VPS)

Setelah diaktifkan di VPS, Anda dan Hermes Agent dapat mengakses endpoint dokumentasi interaktif pada alamat berikut:

| Tipe Dokumentasi | URL Akses | Fungsi / Kegunaan |
| :--- | :--- | :--- |
| **Interactive Swagger UI** | `http://<IP_VPS>:8000/docs` | Eksplorasi interaktif endpoint, schema Pydantic, dan fitur *Try it out*. |
| **Alternative ReDoc UI** | `http://<IP_VPS>:8000/redoc` | Tampilan dokumentasi API clean dan mudah dibaca. |
| **Raw OpenAPI 3.0 JSON** | `http://<IP_VPS>:8000/openapi.json` | Schema machine-readable untuk Hermes Agent (Auto Tool Calling / Function Injection). |

> **Catatan:** Ganti `<IP_VPS>` dengan alamat IP publik server VPS Anda (misalnya `http://123.45.67.89:8000/docs`).

---

## ⚙️ 2. Cara Mengaktifkan Dokumentasi di VPS

Secara default, `ENABLE_DOCS=False`. Untuk mengaktifkannya:

1. Buka atau buat file `.env` di direktori proyek pada VPS:
   ```bash
   nano .env
   ```
2. Tambahkan / pastikan variabel berikut aktif:
   ```env
   # Aktifkan Swagger UI & OpenAPI JSON
   ENABLE_DOCS=true

   # Host dan Port
   HOST=0.0.0.0
   PORT=8000

   # Kunci Keamanan API (Opsional tapi disarankan)
   API_KEY=rahasia_hermes_kamu_123
   ```
3. Restart server Polyfollow di VPS:
   * **Jika menggunakan Docker Compose:**
     ```bash
     docker compose down && docker compose up -d
     ```
   * **Jika menggunakan direct Uvicorn / systemd:**
     ```bash
     uvicorn app.main:app --host 0.0.0.0 --port 8000
     ```
4. Pastikan port 8000 sudah dibuka pada firewall VPS:
   ```bash
   sudo ufw allow 8000/tcp
   ```

---

## 🤖 3. Spesifikasi Endpoint Kunci untuk Hermes Agent

### A. Endpoint Sinyal Konsensus (Utama)
Mengambil agregasi sinyal bandar terbaik berdasarkan akumulasi volume dan konvergensi multi-whale:
* **Method & Path:** `GET /api/v1/signals/consensus`
* **Query Parameters:**
  * `timeframe`: `1h`, `6h`, `24h` (default: `24h`)
  * `min_score`: Batas skor confidence minimal (misal `75` atau `80`)
  * `min_whales`: Jumlah minimal whale yang berpartisipasi (default `2`)
* **Headers:**
  * `X-API-Key: <API_KEY>` (jika `API_KEY` diaktifkan di VPS)
  * `Accept: application/json`

#### Contoh Respons JSON:
```json
[
  {
    "market_id": "0x1234abcd...",
    "market_question": "Will Donald Trump create a Bitcoin strategic reserve?",
    "timeframe": "24h",
    "consensus_outcome": "YES",
    "confidence_score": 84.5,
    "has_conflict": false,
    "actionable_signal": {
      "recommended_action": "BUY_YES",
      "risk_tier": "LOW",
      "suggested_max_entry_price": 0.62,
      "current_market_price": 0.58
    },
    "ai_rationale": "Strong accumulation by 3 Tier-1 whales with 84.5 confidence score and 0 conflicting trades."
  }
]
```

### B. 🚨 Endpoint Whale Exit & Dump Radar (Proteksi TP/SL)
Mengambil sinyal pelepasan posisi, profit taking, atau panic dump oleh bandar untuk memicu Take-Profit / Stop-Loss terotomatisasi:
* **Method & Path:** `GET /api/v1/signals/exits`
* **Query Parameters:**
  * `timeframe`: `1h`, `6h`, `24h` (default: `24h`)
  * `min_exit_usd`: Minimal total volume penjualan dalam USDC (default: `1000.0`)
  * `min_whales`: Jumlah minimal whale yang menjual di market yang sama (default: `1`)
* **Headers:**
  * `X-API-Key: <API_KEY>`
  * `Accept: application/json`

#### Contoh Respons JSON:
```json
[
  {
    "condition_id": "0x1234abcd...",
    "market_title": "Will Solana ETF be approved in 2026?",
    "outcome_exited": "YES",
    "timeframe": "24h",
    "exiting_whales_count": 2,
    "total_exit_volume_usdc": 22000.0,
    "average_exit_price": 0.80,
    "exit_type": "WHALE_EXODUS",
    "urgency": "CRITICAL",
    "recommended_action": "EMERGENCY_CLOSE",
    "is_full_exit": true,
    "exiting_whales": [
      {
        "address": "0xabc...",
        "label": "Whale Alpha",
        "sold_volume_usdc": 12000.0,
        "sold_shares": 15000.0,
        "average_exit_price": 0.80,
        "remaining_shares": 0.0,
        "is_position_cleared": true,
        "archetype": "INSIDER_SPECIALIST"
      }
    ],
    "ai_rationale": "CRITICAL EXIT ALERT: 2 whale(s) executed major liquidations on YES in 'Will Solana ETF be approved in 2026?' totaling $22,000 USDC within 24h. Full liquidation confirmed (0 remaining shares). Immediate exit strongly advised."
  }
]
```

### C. Endpoint Status & Healthcheck
* **Method & Path:** `GET /health`
* **Kegunaan:** Pengecekan status ketersediaan server oleh bot/monitoring tanpa perlu API Key.

---

## 🧪 4. Perintah Pengujian & Verifikasi

Uji akses dari terminal komputer Anda:
```bash
# 1. Pastikan Swagger UI aktif (HTTP 200)
curl -I http://<IP_VPS>:8000/docs

# 2. Cek OpenAPI JSON Schema
curl -s http://<IP_VPS>:8000/openapi.json | head -n 15

# 3. Uji pemanggilan sinyal konsensus dengan API Key
curl -X GET "http://<IP_VPS>:8000/api/v1/signals/consensus?timeframe=24h&min_score=75" \
     -H "X-API-Key: rahasia_hermes_kamu_123"
```

---

## 📋 5. Riwayat Keputusan Desain (Decision Log)
* **D-01**: Menggunakan dokumentasi live interaktif FastAPI Swagger UI (`/docs`), ReDoc (`/redoc`), dan OpenAPI schema (`/openapi.json`).
* **D-02**: Lingkungan deployment berada di VPS.
* **D-03**: Menghubungkan langsung via port VPS (`:8000`) dengan flag `ENABLE_DOCS=true`.
* **D-04**: Autentikasi menggunakan header `X-API-Key` untuk endpoint data, dengan endpoint dokumentasi tetap terbuka publik untuk inspeksi.
