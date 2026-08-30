# 🐋 Polyfollow - Polymarket Whale/Bandar Tracker & Smart Consensus Engine

Backend service otomatis berbasis **Python 3.12+ (FastAPI + Async SQLAlchemy 2.0 + PostgreSQL)** untuk melacak aktivitas posisi, trade history, dan **Smart Signal Scoring (Whale Consensus)** di Polymarket secara real-time.

Layanan ini dirancang khusus untuk menjadi **sumber data & sinyal berbobot tinggi (*high-conviction signals*)** yang siap dikonsumsi oleh **Hermes AI Agent** di VPS lain.

> 📘 **Panduan Analisa Lengkap**: Baca panduan strategi analisa 3-lapis, matriks indikator, dan checklist sinyal di [**docs/PLAYBOOK.md**](docs/PLAYBOOK.md).

---

## 🚀 Fitur Utama

- **Real-Time Data Ingestion**: Mengambil data posisi aktif dan trade history langsung dari Polymarket Data API.
- **Embedded Async Background Poller**: Worker otomatis di dalam proses FastAPI dengan interval polling yang dapat disesuaikan.
- **🧠 Smart Signal Scoring & Whale Consensus**:
  - Mendeteksi konvergensi beberapa whale yang masuk ke outcome market yang sama.
  - Formula Multi-Factor Confidence Scoring (0 - 100): *Whale Count Multiplier (40%) + Volume USD Weight (30%) + Win Rate Reputation (30%) - Conflict Penalty*.
  - Multi-tier rolling timeframes: `1h` (Momentum), `6h`, `24h` (Akumulasi), dan `7d`.
  - Structured **AI Rationale** deskriptif yang siap disuntikkan ke prompt Hermes LLM Agent.
- **Signal Feed for Hermes Agent**: Feed transaksi whale yang belum dibaca (`unread_only=true`) dengan mekanisme `mark-read` untuk mencegah duplikasi sinyal.
- **Async Database Layer**: PostgreSQL + SQLAlchemy 2.0 Async + asyncpg dengan migrasi skema otomatis menggunakan Alembic.
- **Docker-Ready**: Dilengkapi `Dockerfile` dan `docker-compose.yml` untuk instalasi 1-klik di VPS.

---

## 🏗️ Struktur Arsitektur

```
polyfollow/
├── alembic/                # Database migrations
├── app/
│   ├── api/
│   │   └── v1/             # Router endpoints (/wallets, /positions, /trades, /signals, /stats)
│   ├── core/
│   │   ├── config.py       # Pydantic Settings (.env loader)
│   │   ├── database.py     # SQLAlchemy Async engine & session
│   │   └── logging.py      # Structured logging
│   ├── models/             # SQLAlchemy ORM models (Wallet, Position, Trade, Snapshot)
│   ├── schemas/            # Pydantic validation models (Request/Response DTO)
│   ├── services/
│   │   ├── polymarket.py   # Polymarket Data API client (httpx async)
│   │   ├── tracker.py      # Business logic sinkronisasi & deteksi sinyal
│   │   └── consensus.py    # Smart Signal Scoring & Whale Consensus Engine
│   └── workers/
│       └── poller.py       # Async background worker loop
├── tests/                  # Test suite (pytest + pytest-asyncio)
├── docker-compose.yml      # PostgreSQL + API orchestrator
├── Dockerfile              # Container image
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
└── main.py                 # Application entrypoint
```

## 🖥️ Modern Web Dashboard (Dark Mode)

Aplikasi kini dilengkapi **Interactive Web Dashboard** yang responsif dan dapat diakses langsung melalui browser di:
👉 **`http://<IP_VPS>:8000/dashboard`**

**Fitur Dashboard:**
- 📊 **Real-time Overview Cards**: Status live poller, jumlah wallet bandar aktif, sinyal konsensus aktif, dan posisi terbuka.
- 🎯 **Smart Consensus Alpha Feed**: Kartu sinyal interaktif lengkap dengan Action Badge (`BUY_YES`/`BUY_NO`), Risk Tier, Max Entry Price, Dominant Archetype, dan tombol 1-klik *"Copy AI Rationale"*.
- ⚡ **Live Raw Trade Stream**: Tabel transaksi bandar real-time lengkap dengan link ke Polygonscan.
- 🛠️ **Whale Management & Quick Actions**: Tombol 1-klik untuk *Discover Whales*, *Track Wallet Baru*, *Force Sync*, dan *Test Webhook Hermes Agent*.

---

## 📡 REST API Reference (Untuk Hermes Agent)

Dokumentasi interaktif OpenAPI/Swagger UI tersedia di `http://<IP_VPS>:8000/docs`.

### 1. 🧠 Smart Signals & Whale Consensus (Rekomendasi Utama untuk Hermes Agent)
- `GET /api/v1/signals/consensus?timeframe=24h&min_score=50&min_whales=2&limit=20`
  Mengambil sinyal konsensus pintar dari pasar di mana para whale sepakat mengambil posisi yang sama.
  
  **Contoh Response:**
  ```json
  [
    {
      "condition_id": "0xabc123...",
      "market_title": "Will Fed cut interest rates in June 2026?",
      "market_slug": "fed-rate-cut-june-2026",
      "consensus_outcome": "YES",
      "confidence_score": 88.5,
      "strength": "STRONG_CONSENSUS",
      "whale_count": 2,
      "total_volume_usdc": 21200.0,
      "average_entry_price": 0.606,
      "participating_whales": [
        {
          "address": "0xaaaa...aaaa",
          "label": "Whale Alpha",
          "side": "BUY",
          "outcome": "YES",
          "size_usdc": 15000.0,
          "entry_price": 0.60,
          "win_rate": 0.80,
          "trade_count": 1,
          "archetype": "INSIDER_SPECIALIST",
          "conviction_tier": "TIER_1_ELITE"
        }
      ],
      "has_conflict": false,
      "conflict_whale_count": 0,
      "actionable_signal": {
        "recommended_action": "BUY_YES",
        "risk_tier": "LOW",
        "suggested_max_entry_price": 0.656,
        "current_entry_price": 0.606,
        "potential_roi_percent": 65.0,
        "urgency": "CRITICAL"
      },
      "smart_money_breakdown": {
        "total_whales": 2,
        "insider_specialist_count": 1,
        "mega_volume_whales_count": 1,
        "dominant_archetype": "INSIDER_SPECIALIST",
        "average_whale_win_rate": 0.80,
        "volume_concentration_index": 0.58,
        "is_sybil_cluster_suspected": false
      },
      "market_velocity": {
        "price_drift": 0.025,
        "price_trend": "UPWARD_ACCUMULATION",
        "timeframe_volume_usdc": 21200.0
      },
      "ai_rationale": "[STRONG_CONSENSUS] 2 whale(s) (INSIDER_SPECIALIST) accumulated $21,200.00 on YES @ avg 0.606. Avg win rate: 80.0%, Trend: UPWARD_ACCUMULATION (drift: +0.025). Action: BUY_YES (Risk: LOW, Max safe entry: 0.656, Upside: +65.0%). No conflicting whale positions detected.",
      "first_trade_at": "2026-08-26T18:00:00Z",
      "last_trade_at": "2026-08-26T19:30:00Z"
    }
  ]
  ```
- `POST /api/v1/signals/test-webhook` : Menguji pengiriman push alert real-time ke Hermes Agent / Telegram.

### 2. Feed Sinyal Trade Mentah (Raw Trades Feed)
- `GET /api/v1/trades/feed?unread_only=true&limit=50`
  Mengambil transaksi mentah whale yang belum diproses oleh Hermes Agent.
- `POST /api/v1/trades/mark-read`
  Menandai ID trade yang sudah diproses agar tidak dikirim ulang.
  ```json
  {
    "trade_ids": ["c3a9f0f8-2831-482a-a92c-80a5bf296068"]
  }
  ```

### 3. Manajemen & Auto-Discovery Wallet Bandar
- `GET /api/v1/wallets` : Menampilkan seluruh wallet yang dipantau.
- `POST /api/v1/wallets` : Mendaftarkan wallet baru untuk dilacak (otomatis memicu initial sync).
- `POST /api/v1/wallets/discover` : Memicu auto-discovery otomatis whale/bandar dari top markets dan recent trades.
- `POST /api/v1/wallets/seed` : Melakukan re-seeding manual daftar curated top whale wallets.
- `GET /api/v1/wallets/{address}` : Detail informasi wallet.
- `GET /api/v1/wallets/{address}/profile` : Analisis profil intelijen bandar (Archetype, Conviction Tier, Win Rate, Volume).
- `DELETE /api/v1/wallets/{address}` : Menghapus wallet dari pelacakan.
- `POST /api/v1/wallets/{address}/sync` : Memaksa sinkronisasi manual.

### 4. Posisi Terbuka (Open Positions)
- `GET /api/v1/positions` : Menampilkan seluruh posisi terbuka saat ini (`?wallet_address=0x...`).

### 5. Statistik Performa & Health
- `GET /api/v1/wallets/{address}/statistics` : Menampilkan statistik volume, win rate, dan PnL.
- `GET /health` : Mengecek status service, koneksi database, dan status background poller.

---

## 💻 Panduan Pengembangan Lokal (Local Development)

```bash
# 1. Clone repository
git clone https://github.com/your-username/polyfollow.git
cd polyfollow

# 2. Buat virtual environment
uv venv
source .venv/bin/activate

# 3. Install dependensi
uv pip install -r requirements.txt

# 4. Salin template .env
cp .env.example .env

# 5. Jalankan migrasi database
alembic upgrade head

# 6. Jalankan automated test suite
pytest -v

# 7. Jalankan server lokal
python main.py
```
Akses Swagger UI di: `http://localhost:8000/docs`

---

## 🌐 Panduan Langkah-demi-Langkah Install di VPS

### Langkah 1: Install Docker di VPS
```bash
ssh root@<IP_VPS_ANDA>

sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ufw

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### Langkah 2: Clone & Jalankan via Docker Compose
```bash
cd /opt
git clone <URL_REPO_POLYFOLLOW> polyfollow
cd polyfollow

cp .env.example .env
docker compose up -d --build
```

### Langkah 3: Buka Port Firewall
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

### Langkah 4: Uji Coba dari VPS Hermes Agent
```bash
# Cek Smart Consensus Signals
curl "http://<IP_VPS_POLYFOLLOW>:8000/api/v1/signals/consensus?timeframe=24h&min_score=50"
```

---

## 🧪 Testing & Quality Assurance

```bash
pytest --cov=app -v
```

---

## 📜 License
MIT License
