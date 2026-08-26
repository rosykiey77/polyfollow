import datetime
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.position import Position
from app.models.wallet import Wallet


@pytest.mark.asyncio
async def test_positions_listing(async_client: AsyncClient, db_session: AsyncSession):
    wallet_addr = "0x5555555555555555555555555555555555555555"

    wallet = Wallet(address=wallet_addr, label="Position Whale", is_active=True)
    db_session.add(wallet)

    pos = Position(
        id=str(uuid.uuid4()),
        wallet_address=wallet_addr,
        condition_id="cond_123",
        market_title="Fed Interest Rate Cut in May",
        outcome="YES",
        size=5000.0,
        avg_price=0.45,
        current_price=0.60,
        unrealized_pnl=750.0,
        cur_value=3000.0,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(pos)
    await db_session.commit()

    # Query all positions
    res = await async_client.get(f"/api/v1/positions?wallet_address={wallet_addr}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["condition_id"] == "cond_123"
    assert data[0]["unrealized_pnl"] == 750.0
