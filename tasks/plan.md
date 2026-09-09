# Technical Implementation Plan: Database Retention & Whale Quota

## 1. Overview & Architecture
Menerapkan auto-pruning riwayat transaksi $> 14$ hari dan kuota 25 wallet aktif dengan degradasi pintar di service Polyfollow.

## 2. Component Dependency Graph
```
app/core/config.py (Settings)
       │
       ▼
app/services/tracker.py (prune_old_trades + discover_and_register_whales degradation)
       │
       ▼
app/workers/poller.py (periodic hook in background loop)
       │
       ▼
tests/ (unit tests & full regression suite)
```

## 3. Implementation Phases & Vertical Slicing
- **Phase 1: Configuration Layer**
  - Menambahkan variabel konfigurasi di `app/core/config.py` dan `.env.example`.
- **Phase 2: Service Logic (Pruning & Quota Degradation)**
  - Mengimplementasikan `prune_old_trades(db)` di `app/services/tracker.py`.
  - Memperbarui `discover_and_register_whales(db)` untuk mengecek `MAX_TRACKED_WALLETS` dan mendegradasi wallet terpasif.
- **Phase 3: Worker Periodic Hook**
  - Menambahkan pengecekan interval `_maybe_prune_trades()` di dalam `BackgroundPoller._poller_loop`.
- **Phase 4: Test Suite & Verification**
  - Menulis pengujian unit untuk pruning dan degradasi kuota.
  - Menjalankan `pytest` lengkap memastikan 27+ test eksisting tetap 100% lulus.

## 4. Risks & Mitigations
| Risiko | Dampak | Strategi Mitigasi |
|---|---|---|
| Seed whale acuan utama terdegradasi | Kehilangan data acuan bandar utama | Mengecualikan alamat di `INITIAL_SEED_WALLETS` dari kandidat degradasi. |
| Database lock saat eksekusi pruning | Poller siklus reguler tertunda | Bungkus dalam transaksi terpisah dengan penanganan `try...except` dan `rollback()`. |
| Sinyal konsensus 7d kehilangan konteks | Sinyal 7d tidak akurat | Retensi diset 14 hari, memberikan margin aman 7 hari ekstra. |
