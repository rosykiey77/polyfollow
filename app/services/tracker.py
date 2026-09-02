import asyncio
import datetime
import uuid
from typing import Any
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import memory_cache
from app.core.config import settings
from app.core.logging import logger
from app.models.position import Position
from app.models.snapshot import Snapshot
from app.models.trade import Trade
from app.models.wallet import Wallet
from app.services.polymarket import PolymarketClient, polymarket_client


# Top known active Polymarket whale/bandar wallets to seed on clean start
INITIAL_SEED_WALLETS = [
    {
        "address": "0x674887d1ac838099a48b629dff53f25b7b87ee08",
        "label": "Whale Alpha (High Volume Trader)",
    },
    {
        "address": "0x31c7cb5562c1ff3603326fcb880b61483f511375",
        "label": "Whale Fresh-Lilac (Active Macro Bandar)",
    },
    {
        "address": "0xdb5ad26b68d77ae966d29e7180147272ab7a3965",
        "label": "Whale 0xDB5 (Top Accumulator)",
    },
    {
        "address": "0x2a69660046d7acc4ab204d7cc5ba78b0776cd2f7",
        "label": "Whale UpTheBlues (Market Mover)",
    },
    {
        "address": "0x2117ae94a97d69b78cbc81b6680a62deb1955c26",
        "label": "Whale Zzzz87 (High Conviction Bandar)",
    },
    {
        "address": "0xbd15da853ba1d19cc7af11f4011c6d03e2dc5f62",
        "label": "Whale Swift-Trader (Crypto / BTC Bandar)",
    },
]


class TrackerService:
    def __init__(self, client: PolymarketClient = polymarket_client):
        self.client = client

    async def seed_initial_wallets(self, db: AsyncSession, force: bool = False) -> int:
        """Seed default top whale wallets if the wallet table is empty or force=True."""
        result = await db.execute(select(func.count(Wallet.address)))
        count = result.scalar_one_or_none() or 0
        if count > 0 and not force:
            return 0

        existing_res = await db.execute(select(Wallet.address))
        existing_addrs = {row[0] for row in existing_res.fetchall()}

        logger.info("Seeding initial top Polymarket whale wallets...")
        seeded = 0
        for w in INITIAL_SEED_WALLETS:
            addr = w["address"].strip().lower()
            if addr not in existing_addrs:
                wallet = Wallet(address=addr, label=w["label"], is_active=True)
                db.add(wallet)
                existing_addrs.add(addr)
                seeded += 1

        if seeded > 0:
            await db.commit()
            logger.info("Successfully seeded %d whale wallets.", seeded)
        return seeded

    async def discover_and_register_whales(
        self,
        db: AsyncSession,
        top_markets_limit: int = 10,
        max_new_whales: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Dynamically discover active bandar/whale wallets from Polymarket:
        1. Top volume prediction markets (Gamma API) -> Top Holders (Data API)
        2. Real-time high volume trades (Data API)
        Automatically registers new wallets and triggers initial sync.
        """
        effective_limit = max_new_whales if max_new_whales is not None else settings.MAX_NEW_WHALES_PER_DISCOVERY
        logger.info("Running automated Whale/Bandar discovery on Polymarket (limit: %d)...", effective_limit)
        discovered_candidates: dict[str, str] = {}

        # 1. Discover from top volume markets & their holders
        try:
            top_markets = await self.client.get_top_markets(limit=top_markets_limit)
            for market in top_markets:
                cid = market.get("conditionId")
                title = market.get("question") or market.get("title") or "Market"
                if not cid:
                    continue
                holders = await self.client.get_market_holders(cid)
                for h in holders[:5]:  # Top 5 holders per market
                    addr = h.get("proxyWallet") or h.get("user")
                    if addr and len(addr) == 42 and addr.startswith("0x"):
                        clean_addr = addr.strip().lower()
                        label_name = h.get("name") or h.get("pseudonym") or f"Bandar ({title[:25]}...)"
                        if clean_addr not in discovered_candidates:
                            discovered_candidates[clean_addr] = str(label_name)
        except Exception as e:
            logger.warning("Error fetching top market holders during discovery: %s", str(e))

        # 2. Discover from recent trades
        try:
            recent_trades = await self.client.get_recent_trades(limit=50)
            for trade in recent_trades:
                addr = trade.get("proxyWallet") or trade.get("user")
                size = float(trade.get("size") or 0.0)
                price = float(trade.get("price") or 0.0)
                usdc_val = float(trade.get("usdcSize") or (size * price))
                if addr and len(addr) == 42 and addr.startswith("0x") and usdc_val >= 20.0:
                    clean_addr = addr.strip().lower()
                    title = trade.get("title") or "Trade"
                    label_name = trade.get("name") or trade.get("pseudonym") or f"Whale Trader ({title[:25]}...)"
                    if clean_addr not in discovered_candidates:
                        discovered_candidates[clean_addr] = str(label_name)
        except Exception as e:
            logger.warning("Error fetching recent trades during discovery: %s", str(e))

        if not discovered_candidates:
            logger.info("No new whale candidates discovered.")
            return []

        # Check existing wallets in DB
        existing_res = await db.execute(select(Wallet.address))
        existing_addresses = {row[0] for row in existing_res.fetchall()}

        newly_registered: list[dict[str, Any]] = []
        for addr, label in discovered_candidates.items():
            if addr in existing_addresses:
                continue
            if len(newly_registered) >= effective_limit:
                break

            wallet = Wallet(address=addr, label=label, is_active=True)
            db.add(wallet)
            newly_registered.append({"address": addr, "label": label})

        if newly_registered:
            await db.commit()
            logger.info("Discovered and registered %d new whale wallets!", len(newly_registered))
            # Sync each newly registered wallet with event loop friendly spacing
            for item in newly_registered:
                try:
                    await self.sync_wallet(db, item["address"])
                    await asyncio.sleep(0.08)
                except Exception as sync_err:
                    logger.warning("Initial sync error for newly discovered wallet %s: %s", item["address"], str(sync_err))
        else:
            logger.info("All %d discovered whales are already tracked.", len(discovered_candidates))

        return newly_registered


    async def sync_wallet_positions(self, db: AsyncSession, wallet_address: str) -> int:
        """Fetch active positions from Polymarket and replace current DB positions."""
        address = wallet_address.lower()
        raw_positions = await self.client.get_user_positions(address)
        if raw_positions is None:
            return 0

        # Remove existing positions for this wallet
        await db.execute(delete(Position).where(Position.wallet_address == address))

        count = 0
        for item in raw_positions:
            condition_id = str(item.get("conditionId") or item.get("asset") or item.get("market") or "UNKNOWN")
            pos = Position(
                id=str(uuid.uuid4()),
                wallet_address=address,
                condition_id=condition_id,
                asset_id=str(item.get("asset")) if item.get("asset") else None,
                market_title=item.get("title") or item.get("market_title"),
                market_slug=item.get("slug") or item.get("market_slug"),
                outcome=str(item.get("outcome") or "YES").upper(),
                size=float(item.get("size") or 0.0),
                avg_price=float(item.get("avgPrice") or item.get("price") or 0.0),
                current_price=float(item.get("curPrice") or item.get("currentPrice") or 0.0),
                unrealized_pnl=float(item.get("cashPnl") or item.get("pnl") or 0.0),
                cur_value=float(item.get("currentValue") or 0.0),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(pos)
            count += 1

        await db.flush()
        return count

    async def sync_wallet_trades(self, db: AsyncSession, wallet_address: str, limit: int = 50) -> int:
        """Fetch recent trade activities, detect new ones, and store with is_read_by_agent=False."""
        address = wallet_address.lower()
        raw_activity = await self.client.get_user_activity(address, limit=limit)
        if not raw_activity:
            return 0

        # Get existing tx_hashes for this wallet to prevent duplicate insertion
        existing_txs_res = await db.execute(
            select(Trade.transaction_hash).where(
                Trade.wallet_address == address,
                Trade.transaction_hash.isnot(None),
            )
        )
        existing_tx_hashes = {row[0] for row in existing_txs_res.fetchall()}

        new_trades_count = 0
        for act in raw_activity:
            tx_hash = act.get("transactionHash") or act.get("txHash")
            if tx_hash and tx_hash in existing_tx_hashes:
                continue

            # Ensure this is a trading activity
            act_type = str(act.get("type") or "TRADE").upper()
            if act_type not in ("TRADE", "BUY", "SELL", "MATCHED"):
                # Still record if it has size and price
                if not (act.get("size") and act.get("price")):
                    continue

            side = str(act.get("side") or act.get("type") or "BUY").upper()
            if "SELL" in side:
                side = "SELL"
            else:
                side = "BUY"

            traded_at = self.client.parse_timestamp(act.get("timestamp") or act.get("createdAt"))
            size = float(act.get("size") or 0.0)
            price = float(act.get("price") or 0.0)
            usdc_size = float(act.get("usdcSize") or act.get("amount") or (size * price))

            trade = Trade(
                id=str(uuid.uuid4()),
                wallet_address=address,
                transaction_hash=tx_hash,
                condition_id=act.get("conditionId") or act.get("asset"),
                asset_id=act.get("asset"),
                market_title=act.get("title") or act.get("market"),
                market_slug=act.get("slug"),
                side=side,
                outcome=str(act.get("outcome") or "YES").upper() if act.get("outcome") else None,
                size=size,
                price=price,
                usdc_size=usdc_size,
                traded_at=traded_at,
                is_read_by_agent=False,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(trade)
            if tx_hash:
                existing_tx_hashes.add(tx_hash)
            new_trades_count += 1

        await db.flush()
        return new_trades_count

    async def update_wallet_snapshot(self, db: AsyncSession, wallet_address: str) -> Snapshot:
        """Calculate summary statistics and update snapshot for a wallet."""
        address = wallet_address.lower()

        # Count total trades
        total_trades_res = await db.execute(
            select(func.count(Trade.id)).where(Trade.wallet_address == address)
        )
        total_trades = total_trades_res.scalar_one_or_none() or 0

        # Total volume in USDC
        volume_res = await db.execute(
            select(func.sum(Trade.usdc_size)).where(Trade.wallet_address == address)
        )
        total_volume = float(volume_res.scalar_one_or_none() or 0.0)

        # Query active positions to compute count ratio & volume ratio
        positions_res = await db.execute(
            select(Position).where(Position.wallet_address == address)
        )
        positions = positions_res.scalars().all()
        active_positions_count = len(positions)
        total_pnl = sum(float(p.unrealized_pnl or 0.0) for p in positions)
        total_pos_val = sum(float(p.cur_value or 0.0) for p in positions)
        if total_volume <= 0.0 and total_pos_val > 0.0:
            total_volume = total_pos_val

        # Hybrid Smart Money Win-Rate Calculation
        if active_positions_count > 0:
            profitable_positions = [p for p in positions if float(p.unrealized_pnl or 0.0) > 0]
            profit_count = len(profitable_positions)
            ratio_count = profit_count / active_positions_count

            if total_pos_val > 0:
                profit_val = sum(float(p.cur_value or 0.0) for p in profitable_positions)
                ratio_volume = profit_val / total_pos_val
            else:
                ratio_volume = ratio_count

            # Hybrid: 60% position count win ratio + 40% volume conviction ratio
            win_rate = (0.60 * ratio_count) + (0.40 * ratio_volume)
        elif total_trades > 0:
            win_rate = 0.65 if total_volume > 5000.0 else 0.50
        else:
            win_rate = 0.50

        win_rate = max(0.0, min(1.0, round(win_rate, 4)))

        # In-Place Upsert: Check if snapshot already exists for this wallet
        snap_stmt = select(Snapshot).where(Snapshot.wallet_address == address).limit(1)
        existing_snap_res = await db.execute(snap_stmt)
        snapshot = existing_snap_res.scalar_one_or_none()

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if snapshot is not None:
            snapshot.win_rate = win_rate
            snapshot.total_volume_usdc = total_volume
            snapshot.total_pnl_usdc = total_pnl
            snapshot.total_trades_count = total_trades
            snapshot.active_positions_count = active_positions_count
            snapshot.snapshot_date = now_utc
        else:
            snapshot = Snapshot(
                id=str(uuid.uuid4()),
                wallet_address=address,
                win_rate=win_rate,
                total_volume_usdc=total_volume,
                total_pnl_usdc=total_pnl,
                total_trades_count=total_trades,
                active_positions_count=active_positions_count,
                snapshot_date=now_utc,
            )
            db.add(snapshot)

        await db.flush()
        return snapshot


    async def sync_wallet(self, db: AsyncSession, wallet_address: str) -> dict[str, Any]:
        """Perform full synchronization for a single wallet."""
        address = wallet_address.lower()
        logger.info("Syncing wallet %s...", address)
        positions_count = await self.sync_wallet_positions(db, address)
        new_trades_count = await self.sync_wallet_trades(db, address)
        snapshot = await self.update_wallet_snapshot(db, address)

        # Update wallet updated_at timestamp
        wallet_res = await db.execute(select(Wallet).where(Wallet.address == address))
        wallet = wallet_res.scalar_one_or_none()
        if wallet:
            wallet.updated_at = datetime.datetime.now(datetime.timezone.utc)

        await db.commit()
        return {
            "wallet_address": address,
            "positions_synced": positions_count,
            "new_trades_detected": new_trades_count,
            "snapshot_id": snapshot.id,
        }

    async def sync_all_active_wallets(self, db: AsyncSession) -> list[dict[str, Any]]:
        """Fetch all active wallets and synchronize each with event-loop friendly throttling."""
        result = await db.execute(select(Wallet.address).where(Wallet.is_active.is_(True)))
        active_addresses = [row[0] for row in result.fetchall()]

        # If no active wallets exist, seed initial top whales
        if not active_addresses:
            await self.seed_initial_wallets(db)
            result = await db.execute(select(Wallet.address).where(Wallet.is_active.is_(True)))
            active_addresses = [row[0] for row in result.fetchall()]

        results = []
        total_new_trades = 0
        for address in active_addresses:
            try:
                res = await self.sync_wallet(db, address)
                results.append(res)
                total_new_trades += res.get("new_trades_detected", 0)
                # Yield control to event loop so Uvicorn can serve dashboard HTTP requests immediately
                await asyncio.sleep(0.08)
            except Exception as e:
                logger.error("Error syncing wallet %s: %s", address, str(e), exc_info=True)
                await db.rollback()

        # Invalidate signal/metrics cache if fresh activity was recorded
        if total_new_trades > 0:
            await memory_cache.clear()

        return results



tracker_service = TrackerService()
