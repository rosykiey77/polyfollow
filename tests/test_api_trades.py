import datetime
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade import Trade
from app.models.wallet import Wallet


@pytest.mark.asyncio
async def test_trades_feed_and_mark_read(async_client: AsyncClient, db_session: AsyncSession):
    test_wallet = "0x9876543210987654321098765432109876543210"

    # Insert wallet
    wallet = Wallet(address=test_wallet, label="Trader A", is_active=True)
    db_session.add(wallet)

    # Insert mock trades
    trade_1_id = str(uuid.uuid4())
    trade_2_id = str(uuid.uuid4())

    trade1 = Trade(
        id=trade_1_id,
        wallet_address=test_wallet,
        transaction_hash="0xabc111",
        market_title="Will Trump win 2028?",
        side="BUY",
        outcome="YES",
        size=1000.0,
        price=0.55,
        usdc_size=550.0,
        traded_at=datetime.datetime.now(datetime.timezone.utc),
        is_read_by_agent=False,
    )
    trade2 = Trade(
        id=trade_2_id,
        wallet_address=test_wallet,
        transaction_hash="0xabc222",
        market_title="Will Ethereum reach 5k?",
        side="SELL",
        outcome="YES",
        size=500.0,
        price=0.80,
        usdc_size=400.0,
        traded_at=datetime.datetime.now(datetime.timezone.utc),
        is_read_by_agent=False,
    )
    db_session.add_all([trade1, trade2])
    await db_session.commit()

    # 1. Fetch unread trades feed for Hermes Agent
    feed_res = await async_client.get("/api/v1/trades/feed?unread_only=true")
    assert feed_res.status_code == 200
    feed_data = feed_res.json()
    assert len(feed_data) >= 2
    unread_ids = [t["id"] for t in feed_data]
    assert trade_1_id in unread_ids
    assert trade_2_id in unread_ids

    # 2. Mark trade_1 as read
    mark_res = await async_client.post(
        "/api/v1/trades/mark-read",
        json={"trade_ids": [trade_1_id]},
    )
    assert mark_res.status_code == 200
    assert mark_res.json()["marked_count"] == 1

    # 3. Fetch unread feed again -> trade_1 should not appear
    feed_res_after = await async_client.get("/api/v1/trades/feed?unread_only=true")
    assert feed_res_after.status_code == 200
    feed_after_ids = [t["id"] for t in feed_res_after.json()]
    assert trade_1_id not in feed_after_ids
    assert trade_2_id in feed_after_ids
