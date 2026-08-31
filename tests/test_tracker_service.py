import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.wallet import Wallet
from app.models.position import Position
from app.models.trade import Trade
from app.models.snapshot import Snapshot
from app.services.tracker import TrackerService
from app.services.polymarket import PolymarketClient


@pytest.mark.asyncio
async def test_tracker_sync_flow(db_session: AsyncSession):
    test_addr = "0x7777777777777777777777777777777777777777"
    wallet = Wallet(address=test_addr, label="Whale 777", is_active=True)
    db_session.add(wallet)
    await db_session.commit()

    mock_positions = [
        {
            "conditionId": "cond_p1",
            "title": "Election 2028 Outcome",
            "outcome": "YES",
            "size": 2000.0,
            "avgPrice": 0.40,
            "curPrice": 0.60,
            "cashPnl": 400.0,
            "currentValue": 1200.0,
        }
    ]

    mock_activity = [
        {
            "transactionHash": "0xtx_whale_1",
            "conditionId": "cond_p1",
            "title": "Election 2028 Outcome",
            "type": "TRADE",
            "side": "BUY",
            "outcome": "YES",
            "size": 2000.0,
            "price": 0.40,
            "usdcSize": 800.0,
            "timestamp": 1770000000,
        }
    ]

    mock_client = PolymarketClient()
    mock_client.get_user_positions = AsyncMock(return_value=mock_positions)
    mock_client.get_user_activity = AsyncMock(return_value=mock_activity)

    tracker = TrackerService(client=mock_client)

    # 1. Run sync_wallet
    res = await tracker.sync_wallet(db_session, test_addr)
    assert res["positions_synced"] == 1
    assert res["new_trades_detected"] == 1

    # 2. Verify position in DB
    pos_res = await db_session.execute(select(Position).where(Position.wallet_address == test_addr))
    pos = pos_res.scalar_one_or_none()
    assert pos is not None
    assert pos.condition_id == "cond_p1"
    assert pos.size == 2000.0

    # 3. Verify trade in DB has is_read_by_agent=False
    trade_res = await db_session.execute(select(Trade).where(Trade.wallet_address == test_addr))
    trade = trade_res.scalar_one_or_none()
    assert trade is not None
    assert trade.transaction_hash == "0xtx_whale_1"
    assert trade.is_read_by_agent is False

    # 4. Verify snapshot exists
    snap_res = await db_session.execute(select(Snapshot).where(Snapshot.wallet_address == test_addr))
    snap = snap_res.scalar_one_or_none()
    assert snap is not None
    assert snap.total_trades_count == 1
    assert snap.total_volume_usdc == 800.0

    # 5. Run sync again with same activity -> new_trades_detected should be 0 (deduplication)
    res_2 = await tracker.sync_wallet(db_session, test_addr)
    assert res_2["new_trades_detected"] == 0


@pytest.mark.asyncio
async def test_tracker_seed_and_discover(db_session: AsyncSession):
    mock_client = PolymarketClient()
    mock_client.get_top_markets = AsyncMock(return_value=[
        {"conditionId": "cond_m1", "question": "Who wins?", "volume24hr": 50000.0}
    ])
    mock_client.get_market_holders = AsyncMock(return_value=[
        {"proxyWallet": "0x8888888888888888888888888888888888888888", "name": "Whale Boss"}
    ])
    mock_client.get_recent_trades = AsyncMock(return_value=[
        {"proxyWallet": "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee", "name": "Whale Quick", "size": 1000, "price": 0.5, "usdcSize": 500}
    ])
    mock_client.get_user_positions = AsyncMock(return_value=[])
    mock_client.get_user_activity = AsyncMock(return_value=[])

    tracker = TrackerService(client=mock_client)

    # 1. Test seed_initial_wallets
    seeded = await tracker.seed_initial_wallets(db_session, force=True)
    assert seeded > 0

    # 2. Test discover_and_register_whales
    discovered = await tracker.discover_and_register_whales(db_session, top_markets_limit=1, max_new_whales=5)
    assert len(discovered) == 2
    assert any(d["address"] == "0x8888888888888888888888888888888888888888" for d in discovered)
    assert any(d["address"] == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" for d in discovered)


@pytest.mark.asyncio
async def test_hybrid_win_rate_calculation(db_session: AsyncSession):
    test_addr = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    wallet = await db_session.get(Wallet, test_addr)
    if not wallet:
        wallet = Wallet(address=test_addr, label="Whale Accurate", is_active=True)
        db_session.add(wallet)
        await db_session.commit()

    # 1. Add 4 positions: 3 in profit ($3000 total val), 1 in loss ($1000 total val)
    # Total val = $4000. Count ratio = 3/4 = 0.75. Vol ratio = 3000/4000 = 0.75.
    # Hybrid win rate = 0.60 * 0.75 + 0.40 * 0.75 = 0.75 (75%)
    p1 = Position(id="p_h1", wallet_address=test_addr, condition_id="c_h1", unrealized_pnl=100.0, cur_value=1000.0)
    p2 = Position(id="p_h2", wallet_address=test_addr, condition_id="c_h2", unrealized_pnl=200.0, cur_value=1000.0)
    p3 = Position(id="p_h3", wallet_address=test_addr, condition_id="c_h3", unrealized_pnl=300.0, cur_value=1000.0)
    p4 = Position(id="p_h4", wallet_address=test_addr, condition_id="c_h4", unrealized_pnl=-50.0, cur_value=1000.0)
    db_session.add_all([p1, p2, p3, p4])
    await db_session.commit()

    tracker = TrackerService()
    snap = await tracker.update_wallet_snapshot(db_session, test_addr)
    assert snap is not None
    assert snap.win_rate == 0.75
    assert snap.active_positions_count == 4
    assert snap.total_volume_usdc == 4000.0
