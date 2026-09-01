from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import memory_cache
from app.core.config import settings
from app.core.database import async_session_factory, get_db
from app.models.snapshot import Snapshot
from app.models.wallet import Wallet
from app.schemas.wallet import WalletCreate, WalletResponse, WalletUpdate
from app.services.consensus import consensus_service
from app.services.tracker import tracker_service

router = APIRouter(prefix="/wallets", tags=["Wallets"])


async def _run_initial_sync(address: str):
    async with async_session_factory() as session:
        try:
            await tracker_service.sync_wallet(session, address)
            await memory_cache.invalidate_prefix("wallets:")
        except Exception:
            pass


def _build_wallet_response_from_snap(wallet: Wallet, snap: Snapshot | None = None) -> WalletResponse:
    win_rate = snap.win_rate if snap else 0.50
    vol = snap.total_volume_usdc if snap else 0.0
    pnl = snap.total_pnl_usdc if snap else 0.0
    trades_count = snap.total_trades_count if snap else 0
    active_pos = snap.active_positions_count if snap else 0

    archetype, conviction = consensus_service._classify_whale_archetype(
        win_rate=win_rate, size_usdc=vol, trade_count=trades_count
    )

    return WalletResponse(
        address=wallet.address,
        label=wallet.label,
        is_active=wallet.is_active,
        win_rate=round(win_rate, 4),
        total_volume_usdc=round(vol, 2),
        total_pnl_usdc=round(pnl, 2),
        total_trades_count=trades_count,
        active_positions_count=active_pos,
        archetype=archetype.value if hasattr(archetype, "value") else str(archetype),
        conviction_tier=conviction.value if hasattr(conviction, "value") else str(conviction),
        created_at=wallet.created_at,
        updated_at=wallet.updated_at,
    )


async def _build_wallet_response(wallet: Wallet, db: AsyncSession, snap: Snapshot | None = None) -> WalletResponse:
    if snap is None:
        snap_stmt = (
            select(Snapshot)
            .where(Snapshot.wallet_address == wallet.address)
            .order_by(Snapshot.snapshot_date.desc())
            .limit(1)
        )
        snap_res = await db.execute(snap_stmt)
        snap = snap_res.scalar_one_or_none()

    return _build_wallet_response_from_snap(wallet, snap)


@router.get("", response_model=list[WalletResponse])
async def list_wallets(
    active_only: bool = Query(False, description="Filter only active tracked wallets"),
    db: AsyncSession = Depends(get_db),
):
    """List all tracked bandar/whale wallets with performance stats (batch optimized & cached)."""
    cache_key = f"wallets:list:{active_only}"
    cached_data = await memory_cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    query = select(Wallet).order_by(Wallet.created_at.desc())
    if active_only:
        query = query.where(Wallet.is_active.is_(True))
    result = await db.execute(query)
    wallets = result.scalars().all()

    if not wallets:
        return []

    # Single batch query for snapshots to eliminate N+1 database queries
    addresses = [w.address for w in wallets]
    snap_stmt = (
        select(Snapshot)
        .where(Snapshot.wallet_address.in_(addresses))
        .order_by(Snapshot.snapshot_date.desc())
    )
    snap_res = await db.execute(snap_stmt)
    latest_snapshots: dict[str, Snapshot] = {}
    for s in snap_res.scalars().all():
        if s.wallet_address not in latest_snapshots:
            latest_snapshots[s.wallet_address] = s

    responses = [_build_wallet_response_from_snap(w, latest_snapshots.get(w.address)) for w in wallets]
    await memory_cache.set(cache_key, responses, ttl=settings.CACHE_TTL_SECONDS)
    return responses



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
    await memory_cache.invalidate_prefix("wallets:")
    await memory_cache.invalidate_prefix("dashboard:")

    return await _build_wallet_response(wallet, db)


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
    return await _build_wallet_response(wallet, db)


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
    await memory_cache.invalidate_prefix("wallets:")
    await memory_cache.invalidate_prefix("dashboard:")
    return await _build_wallet_response(wallet, db)


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
    await memory_cache.invalidate_prefix("wallets:")
    await memory_cache.invalidate_prefix("dashboard:")
    return None



@router.post("/discover")
async def trigger_whale_discovery(
    top_markets_limit: int = Query(10, ge=1, le=50, description="Number of top volume markets to scan"),
    max_new_whales: int = Query(15, ge=1, le=50, description="Max newly discovered whale wallets to track"),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger automated discovery of active Polymarket whale/bandar wallets
    from top prediction markets and recent large transactions.
    """
    discovered = await tracker_service.discover_and_register_whales(
        db=db,
        top_markets_limit=top_markets_limit,
        max_new_whales=max_new_whales,
    )
    return {
        "message": f"Discovery completed. Registered {len(discovered)} new whale wallets.",
        "discovered_count": len(discovered),
        "discovered_wallets": discovered,
    }


@router.post("/seed")
async def seed_wallets(db: AsyncSession = Depends(get_db)):
    """Seed initial curated top whale wallets into the database."""
    seeded = await tracker_service.seed_initial_wallets(db)
    return {"message": f"Seeding completed. Seeded {seeded} wallets.", "seeded_count": seeded}


@router.get("/{address}/profile")
async def get_whale_profile(address: str, db: AsyncSession = Depends(get_db)):
    """
    Get detailed behavioral intelligence profile for a whale wallet,
    including classified Archetype, Conviction Tier, historical stats, and PnL.
    """
    clean_address = address.strip().lower()
    wallet = await db.get(Wallet, clean_address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {clean_address} not found",
        )

    # Fetch latest snapshot
    from app.models.snapshot import Snapshot
    from app.services.consensus import consensus_service

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

    archetype, tier = consensus_service._classify_whale_archetype(
        win_rate=snapshot.win_rate,
        size_usdc=snapshot.total_volume_usdc,
        trade_count=snapshot.total_trades_count,
    )

    return {
        "address": clean_address,
        "label": wallet.label,
        "is_active": wallet.is_active,
        "archetype": archetype.value,
        "conviction_tier": tier.value,
        "win_rate": snapshot.win_rate,
        "total_volume_usdc": snapshot.total_volume_usdc,
        "total_trades_count": snapshot.total_trades_count,
        "active_positions_count": snapshot.active_positions_count,
        "total_pnl_usdc": snapshot.total_pnl_usdc,
        "created_at": wallet.created_at,
        "updated_at": wallet.updated_at,
    }


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
