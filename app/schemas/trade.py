import datetime
from pydantic import BaseModel, ConfigDict, Field


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wallet_address: str
    transaction_hash: str | None = None
    condition_id: str | None = None
    asset_id: str | None = None
    market_title: str | None = None
    market_slug: str | None = None
    side: str
    outcome: str | None = None
    size: float
    price: float
    usdc_size: float
    traded_at: datetime.datetime
    is_read_by_agent: bool
    created_at: datetime.datetime


class MarkTradesReadRequest(BaseModel):
    trade_ids: list[str] = Field(..., min_length=1, description="List of trade UUIDs to mark as read")


class MarkTradesReadResponse(BaseModel):
    marked_count: int
    success: bool = True
