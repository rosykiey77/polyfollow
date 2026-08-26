from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.position import Position
from app.schemas.position import PositionResponse

router = APIRouter(prefix="/positions", tags=["Positions"])


@router.get("", response_model=list[PositionResponse])
async def list_positions(
    wallet_address: str | None = Query(None, description="Filter positions by wallet address"),
    outcome: str | None = Query(None, description="Filter by outcome (YES, NO)"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
):
    """List open positions across tracked wallets or for a specific wallet."""
    query = select(Position).order_by(Position.cur_value.desc(), Position.updated_at.desc())
    if wallet_address:
        query = query.where(Position.wallet_address == wallet_address.strip().lower())
    if outcome:
        query = query.where(Position.outcome == outcome.strip().upper())

    query = query.limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
