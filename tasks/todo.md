# Implementation Tasks: Database Retention & Whale Quota

- [x] Task 1: Konfigurasi Settings di Config & .env.example
  - Acceptance: `TRADE_RETENTION_DAYS`, `PRUNING_INTERVAL_HOURS`, `ENABLE_AUTO_PRUNING`, dan `MAX_TRACKED_WALLETS = 25` tersedia di `Settings` dan didokumentasikan di `.env.example`.
  - Verify: Jalankan import test python di shell atau pytest.
  - Files: `app/core/config.py`, `.env.example`

- [x] Task 2: Implementasi `prune_old_trades()` di TrackerService
  - Acceptance: Fungsi `prune_old_trades(db)` menghapus semua trade dengan `traded_at < cutoff` secara aman dan mengembalikan jumlah baris yang terhapus.
  - Verify: Unit test memanggil fungsi dan memvalidasi baris terhapus.
  - Files: `app/services/tracker.py`

- [x] Task 3: Implementasi Smart Degradation & Quota 25 di `discover_and_register_whales()`
  - Acceptance: Jika wallet aktif mencapai `MAX_TRACKED_WALLETS` (25), wallet terpasif (di luar initial seed) diubah menjadi `is_active = False` sebelum memasukkan wallet baru.
  - Verify: Unit test memvalidasi rotasi degradasi saat kuota penuh.
  - Files: `app/services/tracker.py`

- [x] Task 4: Hook Periodik Auto-Pruning di Background Poller
  - Acceptance: `BackgroundPoller` mengecek `last_prune_time` dan memanggil `prune_old_trades()` setiap 24 jam secara non-blocking dengan penanganan exception aman.
  - Verify: Unit test memverifikasi `_maybe_prune_trades()` terpanggil saat interval terpenuhi.
  - Files: `app/workers/poller.py`

- [x] Task 5: Penulisan Unit Test Komprehensif & Verifikasi Regresi Penuh
  - Acceptance: Unit test baru untuk pruning & kuota berjalan sukses, dan seluruh test suite eksisting (30 test) tetap lulus 100%.
  - Verify: `pytest` dijalankan dan lulus 100%.
  - Files: `tests/test_retention_and_quota.py`
