import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class TimeframeEnum(str, Enum):
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVEN_DAYS = "7d"


class SignalStrengthEnum(str, Enum):
    STRONG_CONSENSUS = "STRONG_CONSENSUS"
    MODERATE_CONSENSUS = "MODERATE_CONSENSUS"
    WEAK_CONSENSUS = "WEAK_CONSENSUS"


class ParticipatingWhaleInfo(BaseModel):
    address: str
    label: str | None = None
    side: str
    outcome: str
    size_usdc: float
    entry_price: float
    win_rate: float
    trade_count: int


class ConsensusSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition_id: str
    market_title: str | None = None
    market_slug: str | None = None
    consensus_outcome: str
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Confidence score from 0 to 100")
    strength: SignalStrengthEnum
    whale_count: int
    total_volume_usdc: float
    average_entry_price: float
    participating_whales: list[ParticipatingWhaleInfo]
    has_conflict: bool
    conflict_whale_count: int
    ai_rationale: str
    first_trade_at: datetime.datetime
    last_trade_at: datetime.datetime
