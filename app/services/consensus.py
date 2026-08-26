import datetime
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.snapshot import Snapshot
from app.models.trade import Trade
from app.models.wallet import Wallet
from app.schemas.consensus import (
    ConsensusSignalResponse,
    ParticipatingWhaleInfo,
    SignalStrengthEnum,
    TimeframeEnum,
)


class ConsensusService:
    @staticmethod
    def _parse_timeframe(timeframe: str) -> datetime.timedelta:
        mapping = {
            TimeframeEnum.ONE_HOUR: datetime.timedelta(hours=1),
            "1h": datetime.timedelta(hours=1),
            TimeframeEnum.SIX_HOURS: datetime.timedelta(hours=6),
            "6h": datetime.timedelta(hours=6),
            TimeframeEnum.TWENTY_FOUR_HOURS: datetime.timedelta(hours=24),
            "24h": datetime.timedelta(hours=24),
            TimeframeEnum.SEVEN_DAYS: datetime.timedelta(days=7),
            "7d": datetime.timedelta(days=7),
        }
        return mapping.get(timeframe, datetime.timedelta(hours=24))

    async def get_consensus_signals(
        self,
        db: AsyncSession,
        timeframe: str = "24h",
        min_score: float = 50.0,
        min_whales: int = 1,
        limit: int = 20,
    ) -> list[ConsensusSignalResponse]:
        """Aggregate trades in the timeframe window and compute multi-factor consensus signals."""
        delta = self._parse_timeframe(timeframe)
        cutoff = datetime.datetime.now(datetime.timezone.utc) - delta

        # 1. Fetch trades within timeframe
        query = (
            select(Trade)
            .where(
                Trade.traded_at >= cutoff,
                Trade.condition_id.isnot(None),
            )
            .order_by(Trade.traded_at.asc())
        )
        trade_rows = (await db.execute(query)).scalars().all()
        if not trade_rows:
            return []

        # 2. Get wallet labels and win rates
        wallet_addresses = {t.wallet_address for t in trade_rows}
        wallets_res = await db.execute(select(Wallet).where(Wallet.address.in_(wallet_addresses)))
        wallets_map = {w.address: w for w in wallets_res.scalars().all()}

        # Get latest snapshots for win rates
        snapshots_res = await db.execute(
            select(Snapshot).where(Snapshot.wallet_address.in_(wallet_addresses)).order_by(Snapshot.snapshot_date.desc())
        )
        snapshots_map: dict[str, float] = {}
        for s in snapshots_res.scalars().all():
            if s.wallet_address not in snapshots_map:
                snapshots_map[s.wallet_address] = s.win_rate

        # 3. Group trades by condition_id
        markets: dict[str, list[Trade]] = defaultdict(list)
        for t in trade_rows:
            if t.condition_id:
                markets[t.condition_id].append(t)

        signals: list[ConsensusSignalResponse] = []

        for condition_id, trades in markets.items():
            # Group by outcome (e.g. YES vs NO)
            outcome_trades: dict[str, list[Trade]] = defaultdict(list)
            for t in trades:
                out = (t.outcome or "YES").upper()
                outcome_trades[out].append(t)

            # Find dominant outcome by total USDC volume
            dominant_outcome = max(
                outcome_trades.keys(),
                key=lambda o: sum(t.usdc_size for t in outcome_trades[o]),
            )
            dominant_list = outcome_trades[dominant_outcome]
            conflicting_list = [t for o, tlist in outcome_trades.items() if o != dominant_outcome for t in tlist]

            # Aggregate participating whales
            participating_whales_dict: dict[str, dict] = {}
            for t in dominant_list:
                w_addr = t.wallet_address
                if w_addr not in participating_whales_dict:
                    w_obj = wallets_map.get(w_addr)
                    participating_whales_dict[w_addr] = {
                        "address": w_addr,
                        "label": w_obj.label if w_obj else None,
                        "side": t.side,
                        "outcome": dominant_outcome,
                        "size_usdc": 0.0,
                        "total_shares": 0.0,
                        "weighted_price_sum": 0.0,
                        "win_rate": snapshots_map.get(w_addr, 0.55),
                        "trade_count": 0,
                    }
                pw = participating_whales_dict[w_addr]
                pw["size_usdc"] += t.usdc_size
                pw["total_shares"] += t.size
                pw["weighted_price_sum"] += t.price * t.size if t.size > 0 else t.price * t.usdc_size
                pw["trade_count"] += 1

            whale_count = len(participating_whales_dict)
            if whale_count < min_whales:
                continue

            # Conflicting whales count
            conflicting_wallets = {t.wallet_address for t in conflicting_list if t.wallet_address not in participating_whales_dict}
            has_conflict = len(conflicting_wallets) > 0
            conflict_count = len(conflicting_wallets)

            # Total volume & weighted average price
            total_volume = sum(t.usdc_size for t in dominant_list)
            total_shares = sum(t.size for t in dominant_list)
            if total_shares > 0:
                avg_price = sum(t.price * t.size for t in dominant_list) / total_shares
            else:
                avg_price = sum(t.price for t in dominant_list) / len(dominant_list) if dominant_list else 0.0

            # 4. Multi-Factor Scoring Calculation (0 - 100)
            # S_whales (max 40 pts)
            if whale_count >= 3:
                s_whales = 40.0
            elif whale_count == 2:
                s_whales = 30.0
            else:
                s_whales = 15.0

            # S_vol (max 30 pts)
            if total_volume > 10000.0:
                s_vol = 30.0
            elif total_volume >= 1000.0:
                s_vol = 20.0
            else:
                s_vol = 10.0

            # S_rep (max 30 pts)
            avg_win_rate = (
                sum(pw["win_rate"] for pw in participating_whales_dict.values()) / whale_count
                if whale_count > 0
                else 0.50
            )
            s_rep = avg_win_rate * 30.0

            # P_conflict penalty (25 pts per conflicting whale)
            p_conflict = conflict_count * 25.0

            raw_score = s_whales + s_vol + s_rep - p_conflict
            confidence_score = max(0.0, min(100.0, round(raw_score, 1)))

            if confidence_score < min_score:
                continue

            # Determine Strength
            if confidence_score >= 80.0:
                strength = SignalStrengthEnum.STRONG_CONSENSUS
            elif confidence_score >= 50.0:
                strength = SignalStrengthEnum.MODERATE_CONSENSUS
            else:
                strength = SignalStrengthEnum.WEAK_CONSENSUS

            # Construct participating whales info models
            participating_whales_info = [
                ParticipatingWhaleInfo(
                    address=pw["address"],
                    label=pw["label"],
                    side=pw["side"],
                    outcome=pw["outcome"],
                    size_usdc=round(pw["size_usdc"], 2),
                    entry_price=round(pw["weighted_price_sum"] / pw["total_shares"] if pw["total_shares"] > 0 else avg_price, 4),
                    win_rate=round(pw["win_rate"], 2),
                    trade_count=pw["trade_count"],
                )
                for pw in participating_whales_dict.values()
            ]

            # Generate AI rationale for Hermes LLM reasoning
            market_title = dominant_list[0].market_title or condition_id
            market_slug = dominant_list[0].market_slug
            first_trade = dominant_list[0].traded_at
            last_trade = dominant_list[-1].traded_at

            conflict_str = (
                f" Warning: {conflict_count} tracked whale(s) entered the opposite outcome."
                if has_conflict
                else " No conflicting whale positions detected in this window."
            )
            ai_rationale = (
                f"{strength.value.replace('_', ' ').title()}: {whale_count} tracked whale(s) entered {dominant_outcome} "
                f"with total volume ${total_volume:,.2f} USDC (avg price {avg_price:.3f}). "
                f"Historical average win rate is {avg_win_rate * 100:.1f}%.{conflict_str}"
            )

            signals.append(
                ConsensusSignalResponse(
                    condition_id=condition_id,
                    market_title=market_title,
                    market_slug=market_slug,
                    consensus_outcome=dominant_outcome,
                    confidence_score=confidence_score,
                    strength=strength,
                    whale_count=whale_count,
                    total_volume_usdc=round(total_volume, 2),
                    average_entry_price=round(avg_price, 4),
                    participating_whales=participating_whales_info,
                    has_conflict=has_conflict,
                    conflict_whale_count=conflict_count,
                    ai_rationale=ai_rationale,
                    first_trade_at=first_trade,
                    last_trade_at=last_trade,
                )
            )

        # Sort signals by confidence score descending, then volume descending
        signals.sort(key=lambda s: (s.confidence_score, s.total_volume_usdc), reverse=True)
        return signals[:limit]


consensus_service = ConsensusService()
