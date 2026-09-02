import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import memory_cache
from app.core.config import settings
from app.core.database import get_db
from app.models.position import Position
from app.models.trade import Trade
from app.models.wallet import Wallet
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.consensus import consensus_service
from app.workers.poller import poller

router = APIRouter(prefix="/dashboard", tags=["Dashboard Summary"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Fast consolidated aggregate metrics for the dashboard overview cards.
    Runs fast count aggregations in SQL and caches result in memory (< 10ms response).
    """
    cache_key = "dashboard:summary"
    cached = await memory_cache.get(cache_key)
    if cached is not None:
        return cached

    # Fast indexed counts
    wallets_total_res = await db.execute(select(func.count(Wallet.address)))
    total_wallets = wallets_total_res.scalar_one_or_none() or 0

    active_wallets_res = await db.execute(select(func.count(Wallet.address)).where(Wallet.is_active.is_(True)))
    active_wallets = active_wallets_res.scalar_one_or_none() or 0

    pos_count_res = await db.execute(select(func.count(Position.id)))
    total_positions = pos_count_res.scalar_one_or_none() or 0

    trades_count_res = await db.execute(select(func.count(Trade.id)))
    total_trades = trades_count_res.scalar_one_or_none() or 0

    volume_res = await db.execute(select(func.sum(Trade.usdc_size)))
    total_vol = float(volume_res.scalar_one_or_none() or 0.0)

    # Fast signal count from active condition positions (instant < 1ms indexed count)
    active_cond_res = await db.execute(
        select(func.count(func.distinct(Position.condition_id))).where(Position.cur_value > 0)
    )
    total_signals = active_cond_res.scalar_one_or_none() or 0


    summary = DashboardSummaryResponse(
        status="healthy" if poller.is_running else "degraded",
        database="connected",
        poller_running=poller.is_running,
        total_wallets=total_wallets,
        active_wallets=active_wallets,
        total_signals=total_signals,
        total_positions=total_positions,
        total_trades_tracked=total_trades,
        total_volume_tracked_usdc=round(total_vol, 2),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    await memory_cache.set(cache_key, summary, ttl=settings.CACHE_TTL_SECONDS)
    return summary
