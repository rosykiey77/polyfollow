# 📘 Polymarket Whale Intelligence & Trading Playbook

Panduan strategi analisa, framework penyaringan sinyal, dan integrasi keputusan untuk **Polyfollow & Hermes AI Agent**.

---

## 🏛️ 1. Framework 3-Lapis Penyaringan Sinyal (High-Conviction Filter)

Jangan mengeksekusi semua sinyal secara mentah. Gunakan filter 3-lapis untuk memastikan win-rate maksimal:

```
┌─────────────────────────────────────────────────────────────┐
│  LAPIS 1: Saring Confidence Score (Skor >= 80)              │
│  → Menjamin ada konvergensi bandar & volume signifikan      │
├─────────────────────────────────────────────────────────────┤
│  LAPIS 2: Periksa Archetype Bandar                          │
│  → Prioritaskan INSIDER_SPECIALIST & MEGA_VOLUME_BANDAR     │
├─────────────────────────────────────────────────────────────┤
│  LAPIS 3: Validasi Max Safe Entry & Upside ROI              │
│  → Pastikan harga pasar saat ini belum terlambat            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 2. Matriks Indikator & Nilai Ideal

| Indikator | Definisi & Formula | Nilai Ideal | Tindakan Rekomendasi |
| :--- | :--- | :--- | :--- |
| **`confidence_score`** | Skor gabungan jumlah bandar (40%) + volume (30%) + win rate (30%) - penalti konflik. | **`>= 80.0`** (*Strong Consensus*) | Siap dieksekusi dengan size normal. |
| **`dominant_archetype`** | Karakter utama bandar yang mendominasi posisi pasar. | **`INSIDER_SPECIALIST`** (Win Rate > 75%) | Bobot keyakinan tertinggi (*Tier-1 Elite*). |
| **`actionable_signal.recommended_action`** | Aksi langsung yang dihitung berdasarkan konvergensi & harga. | **`BUY_YES`** atau **`BUY_NO`** | Eksekusi sesuai outcome yang direkomendasikan. |
| **`actionable_signal.risk_tier`** | Tingkat risiko sinyal (`LOW`, `MEDIUM`, `HIGH`). | **`LOW`** | Risiko terendah (didukung mult-whale tanpa konflik). |
| **`suggested_max_entry_price`** | Batas toleransi harga masuk tertinggi sebelum risk/reward memburuk. | **`Current Price <= Max Entry`** | Jangan kejar harga (*chase price*) jika sudah di atas nilai ini. |
| **`market_velocity.price_trend`** | Arah pergerakan odds pasar selama periode akumulasi. | **`UPWARD_ACCUMULATION`** | Bandar terus menambah posisi walau harga naik (*Aggressive Fill*). |
| **`has_conflict`** | Apakah terdapat bandar lain yang masuk di outcome berlawanan. | **`false`** (*0 Conflict*) | Jika `true`, pasar berpotensi sideways/volatil. |

---

## ⏱️ 3. Strategi Pemilihan Timeframe

* **`1h` (Momentum / News Scalping)**:
  - Gunakan saat ada *breaking news* (misal: rilis data ekonomi, pengumuman hukum/regulasi).
  - Mengukur kecepatan reaksi bandar sebelum pasar publik merespons.
* **`6h - 24h` (Akumulasi Bandar - *Rekomendasi Utama*)**:
  - *Sweet spot* untuk swing trading. Menunjukkan bandar menyerap likuiditas pasar secara bertahap tanpa membuat harga melonjak drastis.
* **`7d` (Penempatan Posisi Makro)**:
  - Analisis posisi institusional pada pasar berdurasi panjang (Pemilu, Suku Bunga Fed, dll).

---

## 🚦 4. Rambu-Rambu Sinyal (Signal Checklist)

### ✅ Sinyal EMAS (Eksekusi Penuh):
1. **Confidence Score `>= 80.0`** dengan `strength: STRONG_CONSENSUS`.
2. Didukung **2+ Whale** dengan Archetype `INSIDER_SPECIALIST`.
3. Total akumulasi volume **`> $15,000 USDC`**.
4. **Tidak ada conflict whale** (`has_conflict = false`).
5. Harga pasar saat ini **masih di bawah `suggested_max_entry_price`** dengan potensi ROI `> 35%`.

### ⚠️ Sinyal HATI-HATI (Tunggu / Kurangi Size):
1. Status `WAIT_PULLBACK`: Harga saat ini sudah mendekati `0.88 - 0.92`, potensi upside sempit.
2. Volume hanya dimonopoli 1 wallet tunggal (*Volume Concentration Index > 0.90*).

### 🚫 Sinyal BAHAYA (Hindari / Lakukan Fade):
1. Terdapat **2+ Conflict Whale** yang bertaruh di arah sebaliknya $\rightarrow$ Terjadi perang modal antar-bandar.
2. Dominant Archetype adalah `FADED_CONTRARIAN` (Win rate historis < 35%) $\rightarrow$ Pertimbangkan mengambil **posisi sebaliknya (*Contrarian Bet*)**.

---

## 🤖 5. Integrasi Eksekusi dengan Hermes AI Agent

Hermes AI Agent dapat mengonsumsi endpoint sinyal konsensus secara otomatis:

```http
GET /api/v1/signals/consensus?timeframe=24h&min_score=75&min_whales=2
```

### Logika Eksekusi untuk Hermes Agent:
```python
if signal.actionable_signal.recommended_action in ["BUY_YES", "BUY_NO"]:
    if signal.actionable_signal.risk_tier == "LOW" and not signal.has_conflict:
        if current_market_price <= signal.actionable_signal.suggested_max_entry_price:
            execute_trade(
                outcome=signal.consensus_outcome,
                max_price=signal.actionable_signal.suggested_max_entry_price,
                allocation_mode="NORMAL",
                rationale=signal.ai_rationale
            )
```

---

## 🛠️ 6. Rutinitas Operasional Harian
1. **Pagi / Siang**: Buka dashboard di `http://<IP_VPS>:8000/dashboard`, klik **"Discover Whales"** untuk menyerap bandar-bandar baru dari top volume markets.
2. **Saat Monitoring**: Periksa kartu *Smart Consensus Alpha* pada timeframe `24h` dan `6h`.
3. **Cek Transaksi Raksasa**: Pantau *Live Whale Feed* untuk mendeteksi transaksi tunggal `> $10,000` sebagai sinyal awal (*early indicator*).
