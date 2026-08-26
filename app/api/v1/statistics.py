from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.snapshot import Snapshot
from app.models.wallet import Wallet
from app.schemas.snapshot import SnapshotResponse
from app.services.tracker import tracker_service

router = APIRouter(prefix="/wallets", tags=["Statistics"])


@router.get("/{address}/statistics", response_model=SnapshotResponse)
async def get_wallet_statistics(address: str, db: AsyncSession = Depends(get_db)):
    """Get latest performance and volume snapshot for a tracked wallet."""
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )

    # Fetch latest snapshot from DB or compute live
    snapshot_query = (
        select(Snapshot)
        .where(Snapshot.wallet_address == clean_address)
        .order_by(Snapshot.snapshot_date.desc())
        .limit(1)
    )
    res = await db.execute(snapshot_query)
    snapshot = res.scalar_one_or_none()

    if not snapshot:
        snapshot = await tracker_service.update_wallet_snapshot(db, clean_address)
        await db.commit()

    return snapshot
