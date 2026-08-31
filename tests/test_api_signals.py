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
    assert "STRONG_CONSENSUS" in signal_a["ai_rationale"]
    assert signal_a["actionable_signal"]["recommended_action"] == "BUY_YES"
    assert signal_a["actionable_signal"]["risk_tier"] == "LOW"
    assert signal_a["actionable_signal"]["potential_roi_percent"] > 0
    assert "smart_money_breakdown" in signal_a
    assert "market_velocity" in signal_a

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
    assert "WARNING" in signal_a_conf["ai_rationale"]


@pytest.mark.asyncio
async def test_consensus_signals_empty_filter(async_client: AsyncClient):
    # Query with impossible whale threshold
    res_empty = await async_client.get("/api/v1/signals/consensus?timeframe=1h&min_whales=50")
    assert res_empty.status_code == 200
    assert res_empty.json() == []


@pytest.mark.asyncio
async def test_signal_webhook_test_endpoint(async_client: AsyncClient):
    # Test test-webhook endpoint
    res = await async_client.post("/api/v1/signals/test-webhook")
    assert res.status_code == 200
    assert "dispatched" in res.json()


@pytest.mark.asyncio
async def test_holdings_consensus_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    from app.models.position import Position

    addr1 = "0x1111111111111111111111111111111111111111"
    addr2 = "0x2222222222222222222222222222222222222222"
    addr3 = "0x3333333333333333333333333333333333333333"

    w1 = Wallet(address=addr1, label="Whale Boss 1", is_active=True)
    w2 = Wallet(address=addr2, label="Whale Boss 2", is_active=True)
    w3 = Wallet(address=addr3, label="Whale Opponent", is_active=True)
    db_session.add_all([w1, w2, w3])

    # Market: Presidential Election
    cond = "cond_presidential_2028"
    pos1 = Position(id="pos_h1", wallet_address=addr1, condition_id=cond, market_title="Presidential 2028", outcome="YES", size=50000.0, avg_price=0.55, cur_value=30000.0, unrealized_pnl=2500.0)
    pos2 = Position(id="pos_h2", wallet_address=addr2, condition_id=cond, market_title="Presidential 2028", outcome="YES", size=40000.0, avg_price=0.58, cur_value=24000.0, unrealized_pnl=800.0)
    pos3 = Position(id="pos_h3", wallet_address=addr3, condition_id=cond, market_title="Presidential 2028", outcome="NO", size=10000.0, avg_price=0.42, cur_value=4000.0, unrealized_pnl=-200.0)
    db_session.add_all([pos1, pos2, pos3])
    await db_session.commit()

    # Query GET /api/v1/signals/holdings
    res = await async_client.get("/api/v1/signals/holdings?min_whales=2")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1

    market = next(m for m in data if m["condition_id"] == cond)
    assert market["total_whales_count"] == 3
    assert market["dominant_outcome"] == "YES"
    assert market["dominance_percentage"] > 80.0
    assert market["verdict"] == "WHALE_BATTLE_CONFLICT"
    assert market["yes_side"]["whale_count"] == 2
    assert market["yes_side"]["total_value_usdc"] == 54000.0
    assert market["no_side"]["whale_count"] == 1
    assert market["no_side"]["total_value_usdc"] == 4000.0
    assert "Whale Battle Conflict" in market["ai_summary"]

