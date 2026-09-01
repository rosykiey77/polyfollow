import datetime
from pydantic import BaseModel, ConfigDict


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    database: str
    poller_running: bool
    total_wallets: int
    active_wallets: int
    total_signals: int
    total_positions: int
    total_trades_tracked: int
    total_volume_tracked_usdc: float
    timestamp: datetime.datetime
