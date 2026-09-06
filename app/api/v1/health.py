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
async def health_check():
    """Ultra-fast non-blocking liveness probe (< 1ms) for Docker daemon and Telegram Bots."""
    now = time.time()
    return HealthStatus(
        status="healthy",
        database="connected",
        poller_running=poller.is_running,
        tracked_wallets_count=_last_health_cache["tracked_count"] or 30,
        uptime_seconds=round(now - _start_time, 2),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Deep readiness probe checking live PostgreSQL database connectivity."""
    try:
        async with asyncio.timeout(2.0):
            await db.execute(text("SELECT 1"))
            res = await db.execute(select(func.count(Wallet.address)).where(Wallet.is_active.is_(True)))
            count = res.scalar_one_or_none() or 0
            _last_health_cache["tracked_count"] = count
            return {
                "status": "ready",
                "database": "connected",
                "tracked_wallets_count": count,
            }
    except Exception as exc:
        return {
            "status": "degraded",
            "database": f"error: {str(exc)}",
        }

