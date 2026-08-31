import datetime
from pydantic import BaseModel, ConfigDict, Field


class WalletCreate(BaseModel):
    address: str = Field(..., description="Ethereum/Polygon wallet address (0x...)")
    label: str | None = Field(None, description="Descriptive label or whale nickname")
    is_active: bool = Field(True, description="Enable or disable tracking")


class WalletUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address: str
    label: str | None = None
    is_active: bool
    win_rate: float = 0.0
    total_volume_usdc: float = 0.0
    total_pnl_usdc: float = 0.0
    total_trades_count: int = 0
    active_positions_count: int = 0
    archetype: str = "STANDARD_WHALE"
    conviction_tier: str = "TIER_2_STRONG"
    created_at: datetime.datetime
    updated_at: datetime.datetime
