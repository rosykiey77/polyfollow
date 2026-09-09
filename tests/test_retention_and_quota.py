import datetime
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.wallet import Wallet
from app.models.trade import Trade
from app.models.snapshot import Snapshot
from app.services.tracker import TrackerService
from app.services.polymarket import PolymarketClient
from app.workers.poller import BackgroundPoller


@pytest.mark.asyncio
async def test_prune_old_trades(db_session: AsyncSession):
    test_addr = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    wallet = await db_session.get(Wallet, test_addr)
    if not wallet:
        wallet = Wallet(address=test_addr, label="Whale Prune Test", is_active=True)
        db_session.add(wallet)
        await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    old_time = now - datetime.timedelta(days=25)   # 25 days old (> 14 days)
    recent_time = now - datetime.timedelta(days=5) # 5 days old (< 14 days)

    trade_old = Trade(
        id="trade_old_1",
        wallet_address=test_addr,
        transaction_hash="0xold_tx_1",
        condition_id="c_old",
        size=100.0,
        price=0.5,
        usdc_size=50.0,
        traded_at=old_time,
    )
    trade_recent = Trade(
        id="trade_recent_1",
        wallet_address=test_addr,
        transaction_hash="0xrecent_tx_1",
        condition_id="c_recent",
        size=200.0,
        price=0.5,
        usdc_size=100.0,
        traded_at=recent_time,
    )
    db_session.add_all([trade_old, trade_recent])
    await db_session.commit()

    tracker = TrackerService()
    deleted_count = await tracker.prune_old_trades(db_session, retention_days=14)
    assert deleted_count >= 1

    # Verify trade_old was pruned
    old_res = await db_session.execute(select(Trade).where(Trade.id == "trade_old_1"))
    assert old_res.scalar_one_or_none() is None

    # Verify trade_recent still exists
    recent_res = await db_session.execute(select(Trade).where(Trade.id == "trade_recent_1"))
    assert recent_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_whale_quota_smart_degradation(db_session: AsyncSession):
    now = datetime.datetime.now(datetime.timezone.utc)

    # Deactivate any pre-existing session wallets to isolate this test scenario
    existing_all = await db_session.execute(select(Wallet))
    for w in existing_all.scalars().all():
        w.is_active = False
    await db_session.commit()

    # Setup exactly 3 active wallets:
    # w_seed: protected initial seed wallet
    # w_active_trader: non-seed with recent trade (active)
    # w_passive_trader: non-seed with older trade (passive)
    seed_addr = "0x674887d1ac838099a48b629dff53f25b7b87ee08" # From INITIAL_SEED_WALLETS
    active_addr = "0x9911991199119911991199119911991199119911"
    passive_addr = "0x9922992299229922992299229922992299229922"
    new_whale_addr = "0x9933993399339933993399339933993399339933"

    for addr, label in [
        (seed_addr, "Seed Whale Alpha"),
        (active_addr, "Active Whale"),
        (passive_addr, "Passive Whale"),
    ]:
        w = await db_session.get(Wallet, addr)
        if not w:
            w = Wallet(address=addr, label=label, is_active=True)
            db_session.add(w)
        else:
            w.is_active = True

    await db_session.commit()

    # Add trades to distinguish activity
    t_active = Trade(
        id="t_act_uniq_1",
        wallet_address=active_addr,
        traded_at=now - datetime.timedelta(hours=2),
        size=100, price=0.5, usdc_size=50,
    )
    t_passive = Trade(
        id="t_pas_uniq_1",
        wallet_address=passive_addr,
        traded_at=now - datetime.timedelta(days=10),
        size=100, price=0.5, usdc_size=50,
    )
    db_session.add_all([t_active, t_passive])
    await db_session.commit()

    # Mock Polymarket API discovery finding 1 brand new whale candidate
    mock_client = PolymarketClient()
    mock_client.get_top_markets = AsyncMock(return_value=[{"conditionId": "cond_new"}])
    mock_client.get_market_holders = AsyncMock(return_value=[{"proxyWallet": new_whale_addr, "name": "New Whaler"}])
    mock_client.get_recent_trades = AsyncMock(return_value=[])
    mock_client.get_user_positions = AsyncMock(return_value=[])
    mock_client.get_user_activity = AsyncMock(return_value=[])

    tracker = TrackerService(client=mock_client)

    # Set MAX_TRACKED_WALLETS = 3 (we currently have 3 active: seed, active, passive)
    # Adding 1 new whale should force degradation of the passive whale (w_passive_trader)
    with patch.object(settings, "MAX_TRACKED_WALLETS", 3):
        registered = await tracker.discover_and_register_whales(
            db_session, top_markets_limit=1, max_new_whales=1
        )
        assert len(registered) == 1
        assert registered[0]["address"] == new_whale_addr

        # Expire session to reload fresh data from DB
        db_session.expire_all()

        # Passive whale should have is_active=False
        pas_wallet = await db_session.get(Wallet, passive_addr)
        assert pas_wallet is not None
        assert pas_wallet.is_active is False

        # Active whale & seed whale should remain is_active=True
        act_wallet = await db_session.get(Wallet, active_addr)
        assert act_wallet is not None
        assert act_wallet.is_active is True

        seed_wallet = await db_session.get(Wallet, seed_addr)
        assert seed_wallet is not None
        assert seed_wallet.is_active is True

        # Total active wallets in DB should still be 3
        active_res = await db_session.execute(select(Wallet).where(Wallet.is_active.is_(True)))
        active_wallets = active_res.scalars().all()
        assert len(active_wallets) == 3


@pytest.mark.asyncio
async def test_background_poller_pruning_hook(db_session: AsyncSession):
    poller = BackgroundPoller()
    assert poller.last_prune_time is None

    with patch.object(settings, "ENABLE_AUTO_PRUNING", True), \
         patch.object(settings, "PRUNING_INTERVAL_HOURS", 24), \
         patch("app.workers.poller.tracker_service.prune_old_trades", new_callable=AsyncMock) as mock_prune:
        
        mock_prune.return_value = 5

        # 1. First run: last_prune_time is None, should trigger prune
        await poller._maybe_prune_trades(db_session)
        assert mock_prune.call_count == 1
        assert poller.last_prune_time is not None

        # 2. Second run immediately: 24h hasn't passed, should NOT trigger prune
        await poller._maybe_prune_trades(db_session)
        assert mock_prune.call_count == 1
