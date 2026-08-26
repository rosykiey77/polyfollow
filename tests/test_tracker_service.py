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
