import datetime
from pydantic import BaseModel, ConfigDict


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wallet_address: str
    win_rate: float
    total_volume_usdc: float
    total_pnl_usdc: float
    total_trades_count: int
    active_positions_count: int
    snapshot_date: datetime.datetime


class HealthStatus(BaseModel):
    status: str
    database: str
    poller_running: bool
    tracked_wallets_count: int
    uptime_seconds: float
    timestamp: datetime.datetime
