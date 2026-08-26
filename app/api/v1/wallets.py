from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import async_session_factory, get_db
from app.models.wallet import Wallet
from app.schemas.wallet import WalletCreate, WalletResponse, WalletUpdate
from app.services.tracker import tracker_service

router = APIRouter(prefix="/wallets", tags=["Wallets"])


async def _run_initial_sync(address: str):
    async with async_session_factory() as session:
        try:
            await tracker_service.sync_wallet(session, address)
        except Exception:
            pass


@router.get("", response_model=list[WalletResponse])
async def list_wallets(
    active_only: bool = Query(False, description="Filter only active tracked wallets"),
    db: AsyncSession = Depends(get_db),
):
    """List all tracked bandar/whale wallets."""
    query = select(Wallet).order_by(Wallet.created_at.desc())
    if active_only:
        query = query.where(Wallet.is_active.is_(True))
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(
    payload: WalletCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Add a new bandar/whale wallet address to track."""
    clean_address = payload.address.strip().lower()
    if not clean_address.startswith("0x") or len(clean_address) != 42:
        raise HTTPException(
            status_code=422,
            detail="Invalid Ethereum/Polygon wallet address format (must start with 0x and be 42 chars)",
        )

    existing = await db.get(Wallet, clean_address)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Wallet {clean_address} is already tracked",
        )

    wallet = Wallet(
        address=clean_address,
        label=payload.label,
        is_active=payload.is_active,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)

    # Trigger background sync for this wallet immediately
    background_tasks.add_task(_run_initial_sync, clean_address)

    return wallet


@router.get("/{address}", response_model=WalletResponse)
async def get_wallet(address: str, db: AsyncSession = Depends(get_db)):
    """Get detailed information of a tracked wallet."""
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )
    return wallet


@router.patch("/{address}", response_model=WalletResponse)
async def update_wallet(
    address: str,
    payload: WalletUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update label or active tracking status of a wallet."""
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )

    if payload.label is not None:
        wallet.label = payload.label
    if payload.is_active is not None:
        wallet.is_active = payload.is_active

    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.delete("/{address}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wallet(address: str, db: AsyncSession = Depends(get_db)):
    """Remove a wallet and its associated positions, trades, and snapshots."""
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )
    await db.delete(wallet)
    await db.commit()
    return None


@router.post("/{address}/sync")
async def sync_wallet_now(address: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger immediate sync for a specific wallet."""
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )
    result = await tracker_service.sync_wallet(db, clean_address)
    return {"message": "Sync completed successfully", "data": result}
