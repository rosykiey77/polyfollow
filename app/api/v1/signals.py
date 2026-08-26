from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.consensus import ConsensusSignalResponse, TimeframeEnum
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
