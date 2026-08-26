import datetime
from pydantic import BaseModel, ConfigDict


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wallet_address: str
    condition_id: str
    asset_id: str | None = None
    market_title: str | None = None
    market_slug: str | None = None
    outcome: str
    size: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    cur_value: float
    updated_at: datetime.datetime
