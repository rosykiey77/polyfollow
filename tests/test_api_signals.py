import datetime
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Snapshot
from app.models.trade import Trade
from app.models.wallet import Wallet


@pytest.mark.asyncio
async def test_consensus_signals_scoring_and_filtering(async_client: AsyncClient, db_session: AsyncSession):
    whale_1_addr = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    whale_2_addr = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    whale_3_addr = "0xcccccccccccccccccccccccccccccccccccccccc"

    # Add Wallets
    w1 = Wallet(address=whale_1_addr, label="Whale Alpha", is_active=True)
    w2 = Wallet(address=whale_2_addr, label="Whale Beta", is_active=True)
    w3 = Wallet(address=whale_3_addr, label="Whale Gamma", is_active=True)
    db_session.add_all([w1, w2, w3])

    # Add Snapshots with win rates
    s1 = Snapshot(
        id=str(uuid.uuid4()),
        wallet_address=whale_1_addr,
        win_rate=0.80,
        total_volume_usdc=50000.0,
        total_trades_count=20,
    )
    s2 = Snapshot(
        id=str(uuid.uuid4()),
        wallet_address=whale_2_addr,
        win_rate=0.70,
        total_volume_usdc=30000.0,
        total_trades_count=15,
    )
    db_session.add_all([s1, s2])

    now = datetime.datetime.now(datetime.timezone.utc)

    # Market A: Both Whale Alpha and Whale Beta buy YES with large volume within 2 hours
    condition_a = "market_fed_cut_2026"
    t1 = Trade(
        id=str(uuid.uuid4()),
        wallet_address=whale_1_addr,
        condition_id=condition_a,
        market_title="Will Fed cut rates in June 2026?",
        market_slug="fed-rate-cut-june-2026",
        side="BUY",
        outcome="YES",
        size=25000.0,
        price=0.60,
        usdc_size=15000.0,
        traded_at=now - datetime.timedelta(hours=2),
    )
    t2 = Trade(
        id=str(uuid.uuid4()),
        wallet_address=whale_2_addr,
        condition_id=condition_a,
        market_title="Will Fed cut rates in June 2026?",
        market_slug="fed-rate-cut-june-2026",
        side="BUY",
        outcome="YES",
        size=10000.0,
        price=0.62,
        usdc_size=6200.0,
        traded_at=now - datetime.timedelta(minutes=30),
    )

    # Market B: Fast Momentum (happened 10 minutes ago)
    condition_b = "market_btc_ath"
    t3 = Trade(
        id=str(uuid.uuid4()),
        wallet_address=whale_1_addr,
        condition_id=condition_b,
        market_title="BTC ATH this month?",
        side="BUY",
        outcome="YES",
        size=5000.0,
        price=0.75,
        usdc_size=3750.0,
        traded_at=now - datetime.timedelta(minutes=10),
    )

    db_session.add_all([t1, t2, t3])
    await db_session.commit()

    # 1. Query consensus for 24h timeframe
    res_24h = await async_client.get("/api/v1/signals/consensus?timeframe=24h&min_score=50")
    assert res_24h.status_code == 200
    signals_24h = res_24h.json()
    assert len(signals_24h) >= 2

    # Check top signal (Market A)
    signal_a = next(s for s in signals_24h if s["condition_id"] == condition_a)
    assert signal_a["whale_count"] == 2
    assert signal_a["consensus_outcome"] == "YES"
    assert signal_a["total_volume_usdc"] == 21200.0
    assert signal_a["confidence_score"] >= 80.0
    assert signal_a["strength"] == "STRONG_CONSENSUS"
    assert signal_a["has_conflict"] is False
    assert len(signal_a["participating_whales"]) == 2
    assert "Strong Consensus" in signal_a["ai_rationale"]

    # 2. Query 1h timeframe -> Market A was traded 2h ago and 30m ago (only 1 trade in 1h window)
    res_1h = await async_client.get("/api/v1/signals/consensus?timeframe=1h&min_whales=2")
    assert res_1h.status_code == 200
    signals_1h = res_1h.json()
    # Market A should not have >=2 whales in 1h timeframe
    assert not any(s["condition_id"] == condition_a for s in signals_1h)

    # 3. Test Conflict Penalty: Whale 3 enters NO on Market A
    t_conflict = Trade(
        id=str(uuid.uuid4()),
        wallet_address=whale_3_addr,
        condition_id=condition_a,
        market_title="Will Fed cut rates in June 2026?",
        side="BUY",
        outcome="NO",
        size=1000.0,
        price=0.38,
        usdc_size=380.0,
        traded_at=now - datetime.timedelta(minutes=15),
    )
    db_session.add(t_conflict)
    await db_session.commit()

    res_conflict = await async_client.get("/api/v1/signals/consensus?timeframe=24h&min_whales=2")
    assert res_conflict.status_code == 200
    signals_conf = res_conflict.json()
    signal_a_conf = next(s for s in signals_conf if s["condition_id"] == condition_a)
    assert signal_a_conf["has_conflict"] is True
    assert signal_a_conf["conflict_whale_count"] == 1
    # Score should be reduced by 25 points penalty
    assert signal_a_conf["confidence_score"] < signal_a["confidence_score"]
    assert "Warning: 1 tracked whale" in signal_a_conf["ai_rationale"]


@pytest.mark.asyncio
async def test_consensus_signals_empty_filter(async_client: AsyncClient):
    # Query with impossible whale threshold
    res_empty = await async_client.get("/api/v1/signals/consensus?timeframe=1h&min_whales=50")
    assert res_empty.status_code == 200
    assert res_empty.json() == []
