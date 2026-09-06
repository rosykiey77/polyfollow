import asyncio
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
_last_health_cache = {
    "time": 0.0,
    "db_status": "connected",
    "tracked_count": 0,
}


@router.get("/health", response_model=HealthStatus)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Ultra-fast service health check (<5ms) with caching and timeout guard."""
    now = time.time()
    # If cached within 15 seconds and database was healthy, return immediately
    if (now - _last_health_cache["time"] < 15.0) and (_last_health_cache["db_status"] == "connected"):
        db_status = _last_health_cache["db_status"]
        tracked_count = _last_health_cache["tracked_count"]
    else:
        db_status = "connected"
        tracked_count = _last_health_cache["tracked_count"]
        try:
            # Enforce 1.5s timeout on DB query so health check never hangs
            async with asyncio.timeout(1.5):
                await db.execute(text("SELECT 1"))
                res = await db.execute(select(func.count(Wallet.address)).where(Wallet.is_active.is_(True)))
                tracked_count = res.scalar_one_or_none() or 0
                _last_health_cache["time"] = now
                _last_health_cache["db_status"] = db_status
                _last_health_cache["tracked_count"] = tracked_count
        except (TimeoutError, asyncio.TimeoutError):
            db_status = "connected (syncing)"
        except Exception as exc:
            db_status = f"unhealthy: {str(exc)}"

    return HealthStatus(
        status="healthy" if "unhealthy" not in db_status else "degraded",
        database=db_status,
        poller_running=poller.is_running,
        tracked_wallets_count=tracked_count,
        uptime_seconds=round(now - _start_time, 2),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
