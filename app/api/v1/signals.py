from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.consensus import (
    ConsensusSignalResponse,
    MarketHoldingsConsensusResponse,
    TimeframeEnum,
)
from app.services.consensus import consensus_service

router = APIRouter(prefix="/signals", tags=["Smart Signals & Consensus"])


@router.get("/consensus", response_model=list[ConsensusSignalResponse])
async def get_consensus_signals(
    timeframe: TimeframeEnum = Query(
        TimeframeEnum.TWENTY_FOUR_HOURS,
        description="Timeframe window for grouping whale consensus: 1h (momentum), 6h, 24h (accumulation), 7d",
    ),
    min_score: float = Query(
        50.0,
        ge=0.0,
        le=100.0,
        description="Minimum confidence score filter (0.0 to 100.0)",
    ),
    min_whales: int = Query(
        1,
        ge=1,
        le=50,
        description="Minimum number of tracked whales agreeing on the same outcome",
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of consensus signals to return",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Smart Signal Scoring & Whale Consensus Engine.
    Detects high-conviction market opportunities where multiple whales take aligned positions,
    calculates multi-factor confidence score (0-100), and provides AI rationale ready for Hermes Agent.
    """
    return await consensus_service.get_consensus_signals(
        db=db,
        timeframe=timeframe.value,
        min_score=min_score,
        min_whales=min_whales,
        limit=limit,
    )


@router.get("/holdings", response_model=list[MarketHoldingsConsensusResponse])
async def get_holdings_consensus(
    min_whales: int = Query(
        1,
        ge=1,
        le=50,
        description="Minimum number of tracked whales holding positions in this market",
    ),
    limit: int = Query(
        30,
        ge=1,
        le=100,
        description="Maximum number of market holdings to analyze",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Portfolio Holdings Radar (YES vs NO Battle Consensus).
    Aggregates all open positions currently held by tracked whales across prediction markets,
    comparing YES vs NO exposure, conviction, dominance %, and detecting whale battles.
    """
    return await consensus_service.get_portfolio_holdings_consensus(
        db=db,
        min_whales=min_whales,
        limit=limit,
    )


@router.post("/test-webhook")
async def test_webhook_dispatch(db: AsyncSession = Depends(get_db)):
    """Test outbound webhook and Telegram alert dispatch with the latest consensus signal."""
    from app.services.webhook import webhook_service

    signals = await consensus_service.get_consensus_signals(db=db, timeframe="7d", min_score=0.0, min_whales=1, limit=1)
    if not signals:
        return {"message": "No signals available to test dispatch", "dispatched": False}

    sample_signal = signals[0].model_dump()
    # Force min score for test dispatch
    sample_signal["confidence_score"] = 99.0
    dispatched = await webhook_service.dispatch_signal_alert(sample_signal)
    return {
        "message": "Webhook test dispatch completed",
        "dispatched": dispatched,
        "signal_tested": sample_signal["market_title"],
    }
