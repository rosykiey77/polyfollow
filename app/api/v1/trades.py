import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.trade import Trade
from app.schemas.trade import (
    MarkTradesReadRequest,
    MarkTradesReadResponse,
    TradeResponse,
)

router = APIRouter(prefix="/trades", tags=["Trades & Signals"])


@router.get("/feed", response_model=list[TradeResponse])
async def get_trades_feed(
    unread_only: bool = Query(True, description="Fetch only trades not yet consumed by Hermes Agent"),
    wallet_address: str | None = Query(None, description="Filter by wallet address"),
    since: datetime.datetime | None = Query(None, description="Filter trades after this timestamp (UTC)"),
    limit: int = Query(50, ge=1, le=200, description="Number of trade records to fetch"),
    db: AsyncSession = Depends(get_db),
):
    """
    Trade signal feed optimized for Hermes Agent ingestion.
    Allows fetching new/unread whale trades with timestamps and pagination.
    """
    query = select(Trade).order_by(Trade.traded_at.desc())

    if unread_only:
        query = query.where(Trade.is_read_by_agent.is_(False))
    if wallet_address:
        query = query.where(Trade.wallet_address == wallet_address.strip().lower())
    if since:
        query = query.where(Trade.traded_at >= since)

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/mark-read", response_model=MarkTradesReadResponse)
async def mark_trades_as_read(
    payload: MarkTradesReadRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a list of trade IDs as consumed/read by Hermes Agent to avoid duplicate signal alerts.
    """
    if not payload.trade_ids:
        return MarkTradesReadResponse(marked_count=0)

    stmt = (
        update(Trade)
        .where(Trade.id.in_(payload.trade_ids))
        .values(is_read_by_agent=True)
    )
    result = await db.execute(stmt)
    await db.commit()
    return MarkTradesReadResponse(marked_count=result.rowcount)
