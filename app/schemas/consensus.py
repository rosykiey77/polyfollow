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


class WhaleArchetypeEnum(str, Enum):
    INSIDER_SPECIALIST = "INSIDER_SPECIALIST"
    MEGA_VOLUME_BANDAR = "MEGA_VOLUME_BANDAR"
    MOMENTUM_SCALPER = "MOMENTUM_SCALPER"
    STANDARD_WHALE = "STANDARD_WHALE"
    FADED_CONTRARIAN = "FADED_CONTRARIAN"


class ConvictionTierEnum(str, Enum):
    TIER_1_ELITE = "TIER_1_ELITE"
    TIER_2_STRONG = "TIER_2_STRONG"
    TIER_3_REGULAR = "TIER_3_REGULAR"


class RecommendedActionEnum(str, Enum):
    BUY_YES = "BUY_YES"
    BUY_NO = "BUY_NO"
    WAIT_PULLBACK = "WAIT_PULLBACK"
    AVOID_CONFLICT = "AVOID_CONFLICT"
    FADE_CONTRARIAN = "FADE_CONTRARIAN"


class RiskTierEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EntryZoneEnum(str, Enum):
    OPTIMAL_SWEET_SPOT = "OPTIMAL_SWEET_SPOT"
    EARLY_SPECULATIVE = "EARLY_SPECULATIVE"
    LATE_OVERBOUGHT = "LATE_OVERBOUGHT"
    AVOID_LATE_FOMO = "AVOID_LATE_FOMO"


class ActionableDecision(BaseModel):
    recommended_action: RecommendedActionEnum
    risk_tier: RiskTierEnum
    entry_zone: EntryZoneEnum = EntryZoneEnum.OPTIMAL_SWEET_SPOT
    suggested_max_entry_price: float
    current_entry_price: float
    potential_roi_percent: float
    urgency: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, or CRITICAL")



class SmartMoneyBreakdown(BaseModel):
    total_whales: int
    insider_specialist_count: int
    mega_volume_whales_count: int
    dominant_archetype: WhaleArchetypeEnum
    average_whale_win_rate: float
    volume_concentration_index: float = Field(..., description="Herfindahl Index (0 to 1), lower means healthier distributed whale backing")
    is_sybil_cluster_suspected: bool = False


class MarketVelocity(BaseModel):
    price_drift: float = Field(0.0, description="Price change from first to last trade in window")
    price_trend: str = Field("STABLE", description="UPWARD_ACCUMULATION, DOWNWARD_PRESSURE, STABLE")
    timeframe_volume_usdc: float


class ParticipatingWhaleInfo(BaseModel):
    address: str
    label: str | None = None
    side: str
    outcome: str
    size_usdc: float
    entry_price: float
    win_rate: float
    trade_count: int
    archetype: WhaleArchetypeEnum = WhaleArchetypeEnum.STANDARD_WHALE
    conviction_tier: ConvictionTierEnum = ConvictionTierEnum.TIER_3_REGULAR


class ConsensusSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition_id: str
    market_title: str | None = None
    market_slug: str | None = None
    consensus_outcome: str
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Multi-factor Confidence score from 0 to 100")
    strength: SignalStrengthEnum
    whale_count: int
    total_volume_usdc: float
    average_entry_price: float
    participating_whales: list[ParticipatingWhaleInfo]
    has_conflict: bool
    conflict_whale_count: int
    actionable_signal: ActionableDecision
    smart_money_breakdown: SmartMoneyBreakdown
    market_velocity: MarketVelocity
    ai_rationale: str
    first_trade_at: datetime.datetime
    last_trade_at: datetime.datetime


class WhaleHoldingInfo(BaseModel):
    address: str
    label: str | None = None
    size: float
    cur_value: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    win_rate: float
    archetype: str = "STANDARD_WHALE"
    conviction_tier: str = "TIER_2_STRONG"


class OutcomeHoldingsBreakdown(BaseModel):
    outcome: str
    whale_count: int
    total_value_usdc: float
    total_shares_size: float
    average_entry_price: float
    current_price: float
    total_unrealized_pnl: float
    whales: list[WhaleHoldingInfo]


class MarketHoldingsConsensusResponse(BaseModel):
    condition_id: str
    market_title: str | None = None
    market_slug: str | None = None
    total_whales_count: int
    total_portfolio_usdc: float
    dominant_outcome: str
    dominance_percentage: float
    verdict: str
    entry_zone: EntryZoneEnum = EntryZoneEnum.OPTIMAL_SWEET_SPOT
    potential_roi_percent: float = 0.0
    confidence_score: float
    yes_side: OutcomeHoldingsBreakdown
    no_side: OutcomeHoldingsBreakdown
    ai_summary: str

