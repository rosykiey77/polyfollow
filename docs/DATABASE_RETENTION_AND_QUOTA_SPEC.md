# Spec: Database Auto-Pruning & Active Whale Quota Management

## Objective
Mencegah pembengkakan ukuran database pada Polyfollow di VPS spesifikasi hemat dan menjaga performa latensi sinyal tetap real-time untuk Hermes AI Agent melalui:
1. **Auto-Pruning Transaksi**: Menghapus transaksi lama pada tabel `trades` yang berumur $> 14$ hari secara berkala di background worker tanpa mengorbankan integritas data konsensus (`7d`) dan metriks performa bandar.
2. **Active Whale Quota & Smart Degradation**: Membatasi kuota maksimal 25 wallet aktif (`is_active = True`). Jika kuota penuh dan ada bandar baru yang ditemukan oleh auto-discovery, mendegradasi bandar paling pasif/terburuk menjadi `is_active = False`.

## Tech Stack
- **Language**: Python 3.12+
- **Framework**: FastAPI, Uvicorn
- **ORM / Database Layer**: SQLAlchemy 2.0 (Async), aiosqlite (lokal) & asyncpg (production)
- **Data Validation & Settings**: Pydantic v2, Pydantic-Settings
- **Test Framework**: Pytest, pytest-asyncio, pytest-cov

## Commands
```bash
# Activate virtual environment
source .venv/bin/activate

# Run test suite
pytest

# Run tests with coverage
pytest --cov=app tests/

# Run dev server
python main.py
# or: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure
```
app/
├── core/
│   ├── config.py             → Tambah settings: TRADE_RETENTION_DAYS, PRUNING_INTERVAL_HOURS, ENABLE_AUTO_PRUNING, MAX_TRACKED_WALLETS
├── services/
│   ├── tracker.py            → Tambah prune_old_trades() dan logika degradasi di discover_and_register_whales()
├── workers/
│   ├── poller.py             → Tambah hook periodik _maybe_prune_trades() dalam _poller_loop
tests/
├── test_tracker_service.py   → Tambah unit test untuk pruning & quota degradation
docs/
└── DATABASE_RETENTION_AND_QUOTA_SPEC.md → Dokumen spesifikasi ini
tasks/
├── plan.md                   → Rencana arsitektur dan mitigasi risiko
└── todo.md                   → Daftar tugas implementasi bertahap
```

## Code Style
- Async/await pattern untuk seluruh interaksi database SQLAlchemy.
- Type annotations lengkap pada setiap fungsi baru.
- Logging terstruktur menggunakan `app.core.logging.logger`.
- Pattern contoh:
```python
async def prune_old_trades(self, db: AsyncSession) -> int:
    """Delete trades older than configured retention period."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=settings.TRADE_RETENTION_DAYS
    )
    stmt = delete(Trade).where(Trade.traded_at < cutoff)
    result = await db.execute(stmt)
    deleted_count = result.rowcount or 0
    await db.commit()
    logger.info("Auto-pruning completed: %d old trades removed.", deleted_count)
    return deleted_count
```

## Testing Strategy
- **Framework**: `pytest` dengan `pytest-asyncio`.
- **Lokasi Tes**: `tests/test_tracker_service.py` & test file baru jika diperlukan.
- **Cakupan Pengujian**:
  1. `test_prune_old_trades`: Memastikan trade $> 14$ hari terhapus dan trade $\le 14$ hari bertahan.
  2. `test_smart_degradation_quota`: Memastikan saat wallet aktif mencapai 25, wallet pasif didegradasi dan total wallet aktif tidak melebihi 25.
  3. `test_consensus_signals_intact`: Memastikan rolling timeframe konsensus (`7d`, `24h`, dll) tetap berfungsi normal.

## Boundaries
- **Always**: Jalankan `pytest` sebelum dan sesudah perubahan kode; pertahankan isolasi transaksi DB (`try/except/rollback`); jaga backwards-compatibility.
- **Ask first**: Mengubah skema kolom database di Alembic migration atau menambah library dependency baru di `requirements.txt`.
- **Never**: Menghapus data wallet fisik secara permanen (`DELETE FROM wallets`); membiarkan background worker crash saat pruning gagal.

## Success Criteria
- [ ] Pengaturan `TRADE_RETENTION_DAYS = 14`, `PRUNING_INTERVAL_HOURS = 24`, `ENABLE_AUTO_PRUNING = True`, dan `MAX_TRACKED_WALLETS = 25` tersedia dan terbaca dari `.env`.
- [ ] Pemanggilan `prune_old_trades()` berhasil menghapus transaksi yang lebih lama dari 14 hari tanpa menyentuh tabel `positions` atau `snapshots`.
- [ ] Auto-discovery menjaga jumlah wallet aktif $\le 25$ dengan mendegradasi wallet paling pasif.
- [ ] Background poller menjalankan pruning setiap 24 jam secara non-blocking.
- [ ] Seluruh 27+ test lulus 100% tanpa regresi.

## Decision Log
| No | Topik | Pilihan yang Diambil | Alasan / Rationale |
|---|---|---|---|
| 1 | Manajemen Ukuran Data | Auto-Pruning 14 Hari | Menjaga database tetap ramping & aman untuk timeframe konsensus tertinggi (`7d`). |
| 2 | Kapasitas Wallet | Kuota 25 Wallet + Auto-Degradasi | Menjaga sinyal tetap *real-time* & membuang akun tidur tanpa menghapus riwayatnya. |
| 3 | Pendekatan Desain | In-Process Poller Hook (Pendekatan A) | Mandiri di dalam background worker FastAPI, hemat I/O, tanpa dependensi eksternal. |
| 4 | Kriteria Degradasi | Pasif Terlama + Win Rate Terendah | Memastikan slot selalu diisi oleh bandar yang paling aktif bergerak di pasar. |
| 5 | Proteksi Seed | Pengecualian Seed Whales Awal | Mencegah bandar acuan utama terdepak sebelum riwayatnya terbentuk. |
