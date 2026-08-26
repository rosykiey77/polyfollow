import datetime
import time
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.wallet import Wallet
from app.schemas.snapshot import HealthStatus
from app.workers.poller import poller

router = APIRouter(tags=["Health"])
_start_time = time.time()


@router.get("/health", response_model=HealthStatus)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check service health, database status, and background poller."""
    db_status = "connected"
    tracked_count = 0
    try:
        await db.execute(text("SELECT 1"))
        res = await db.execute(select(func.count(Wallet.address)).where(Wallet.is_active.is_(True)))
        tracked_count = res.scalar_one_or_none() or 0
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return HealthStatus(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        poller_running=poller.is_running,
        tracked_wallets_count=tracked_count,
        uptime_seconds=round(time.time() - _start_time, 2),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
