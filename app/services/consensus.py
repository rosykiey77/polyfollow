import datetime
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import memory_cache
from app.core.config import settings
from app.models.position import Position
from app.models.snapshot import Snapshot
from app.models.trade import Trade
from app.models.wallet import Wallet

from app.schemas.consensus import (
    ActionableDecision,
    ConsensusSignalResponse,
    ConvictionTierEnum,
    EntryZoneEnum,
    MarketHoldingsConsensusResponse,
    MarketVelocity,

    OutcomeHoldingsBreakdown,
    ParticipatingWhaleInfo,
    RecommendedActionEnum,
    RiskTierEnum,
    SignalStrengthEnum,
    SmartMoneyBreakdown,
    TimeframeEnum,
    WhaleArchetypeEnum,
    WhaleHoldingInfo,
)


def _ensure_utc(val: datetime.datetime | None) -> datetime.datetime:
    """Safely ensure datetime is timezone-aware UTC to prevent timezone subtraction errors."""
    if val is None:
        return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(val, str):
        try:
            val = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)
    if isinstance(val, (int, float)):
        if val > 1e11:
            val = val / 1000.0
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=datetime.timezone.utc)
        return val.astimezone(datetime.timezone.utc)
    return datetime.datetime.now(datetime.timezone.utc)


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

    @staticmethod
    def _classify_whale_archetype(win_rate: float, size_usdc: float, trade_count: int) -> tuple[WhaleArchetypeEnum, ConvictionTierEnum]:
        """Classify whale into behavioral archetype and conviction tier."""
        if win_rate >= 0.75:
            archetype = WhaleArchetypeEnum.INSIDER_SPECIALIST
        elif size_usdc >= 10000.0:
            archetype = WhaleArchetypeEnum.MEGA_VOLUME_BANDAR
        elif trade_count >= 3:
            archetype = WhaleArchetypeEnum.MOMENTUM_SCALPER
        elif win_rate <= 0.35 and win_rate > 0.0:
            archetype = WhaleArchetypeEnum.FADED_CONTRARIAN
        else:
            archetype = WhaleArchetypeEnum.STANDARD_WHALE

        if win_rate >= 0.75 and size_usdc >= 3000.0:
            conviction = ConvictionTierEnum.TIER_1_ELITE
        elif win_rate >= 0.60 or size_usdc >= 1500.0:
            conviction = ConvictionTierEnum.TIER_2_STRONG
        else:
            conviction = ConvictionTierEnum.TIER_3_REGULAR

        return archetype, conviction

    async def get_consensus_signals(
        self,
        db: AsyncSession,
        timeframe: str = "24h",
        min_score: float = 50.0,
        min_whales: int = 1,
        limit: int = 20,
    ) -> list[ConsensusSignalResponse]:
        """Aggregate trades in the timeframe window and compute multi-factor consensus signals."""
        cache_key = f"signals:consensus:{timeframe}:{min_score}:{min_whales}:{limit}"
        cached_result = await memory_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

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

        # Get snapshots for win rates (1 row per wallet)
        snapshots_res = await db.execute(
            select(Snapshot).where(Snapshot.wallet_address.in_(wallet_addresses))
        )
        snapshots_map = {s.wallet_address: s.win_rate for s in snapshots_res.scalars().all()}


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
                        "timestamps": [],
                    }
                pw = participating_whales_dict[w_addr]
                pw["size_usdc"] += t.usdc_size
                pw["total_shares"] += t.size
                pw["weighted_price_sum"] += t.price * t.size if t.size > 0 else t.price * t.usdc_size
                pw["trade_count"] += 1
                pw["timestamps"].append(_ensure_utc(t.traded_at))

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

            # Volume Concentration Index (Herfindahl Index: sum of squared market shares)
            if total_volume > 0:
                concentration_index = round(sum((pw["size_usdc"] / total_volume) ** 2 for pw in participating_whales_dict.values()), 3)
            else:
                concentration_index = 1.0

            # Sybil / Correlated Fast Entry Check (< 180 seconds between different wallets)
            is_sybil_suspected = False
            all_first_times = [_ensure_utc(sorted(pw["timestamps"])[0]) for pw in participating_whales_dict.values() if pw["timestamps"]]
            if len(all_first_times) >= 2:
                time_span = abs((max(all_first_times) - min(all_first_times)).total_seconds())
                if time_span < 180:
                    is_sybil_suspected = True

            # P_conflict penalty (25 pts per conflicting whale)
            p_conflict = conflict_count * 25.0

            # Bonus for healthy decentralized whale backing vs high concentration penalty
            concentration_adj = 5.0 if (concentration_index <= 0.55 and whale_count >= 2) else (-5.0 if concentration_index > 0.90 and whale_count > 1 else 0.0)


            raw_score = s_whales + s_vol + s_rep - p_conflict + concentration_adj
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

            # Construct participating whales info models with archetype classification
            participating_whales_info: list[ParticipatingWhaleInfo] = []
            insider_count = 0
            mega_volume_count = 0

            for pw in participating_whales_dict.values():
                archetype, tier = self._classify_whale_archetype(
                    win_rate=pw["win_rate"],
                    size_usdc=pw["size_usdc"],
                    trade_count=pw["trade_count"],
                )
                if archetype == WhaleArchetypeEnum.INSIDER_SPECIALIST:
                    insider_count += 1
                if pw["size_usdc"] >= 10000.0:
                    mega_volume_count += 1

                entry_p = round(pw["weighted_price_sum"] / pw["total_shares"] if pw["total_shares"] > 0 else avg_price, 4)
                participating_whales_info.append(
                    ParticipatingWhaleInfo(
                        address=pw["address"],
                        label=pw["label"],
                        side=pw["side"],
                        outcome=pw["outcome"],
                        size_usdc=round(pw["size_usdc"], 2),
                        entry_price=entry_p,
                        win_rate=round(pw["win_rate"], 2),
                        trade_count=pw["trade_count"],
                        archetype=archetype,
                        conviction_tier=tier,
                    )
                )

            # Dominant Archetype Calculation
            if insider_count >= 2:
                dominant_archetype = WhaleArchetypeEnum.INSIDER_SPECIALIST
            elif mega_volume_count >= 1:
                dominant_archetype = WhaleArchetypeEnum.MEGA_VOLUME_BANDAR
            elif any(p.archetype == WhaleArchetypeEnum.MOMENTUM_SCALPER for p in participating_whales_info):
                dominant_archetype = WhaleArchetypeEnum.MOMENTUM_SCALPER
            elif any(p.archetype == WhaleArchetypeEnum.FADED_CONTRARIAN for p in participating_whales_info):
                dominant_archetype = WhaleArchetypeEnum.FADED_CONTRARIAN
            else:
                dominant_archetype = WhaleArchetypeEnum.STANDARD_WHALE

            # Market Velocity & Price Drift
            first_trade = _ensure_utc(dominant_list[0].traded_at)
            last_trade = _ensure_utc(dominant_list[-1].traded_at)
            first_p = dominant_list[0].price
            last_p = dominant_list[-1].price

            price_drift = round(last_p - first_p, 4)
            if price_drift > 0.02:
                price_trend = "UPWARD_ACCUMULATION"
            elif price_drift < -0.02:
                price_trend = "DOWNWARD_PRESSURE"
            else:
                price_trend = "STABLE"

            market_velocity = MarketVelocity(
                price_drift=price_drift,
                price_trend=price_trend,
                timeframe_volume_usdc=round(total_volume, 2),
            )

            # Smart Money Breakdown
            smart_money = SmartMoneyBreakdown(
                total_whales=whale_count,
                insider_specialist_count=insider_count,
                mega_volume_whales_count=mega_volume_count,
                dominant_archetype=dominant_archetype,
                average_whale_win_rate=round(avg_win_rate, 2),
                volume_concentration_index=concentration_index,
                is_sybil_cluster_suspected=is_sybil_suspected,
            )

            # Actionable Decision Logic for Hermes Agent
            if has_conflict and conflict_count >= 2:
                recommended_action = RecommendedActionEnum.AVOID_CONFLICT
                risk_tier = RiskTierEnum.HIGH
                urgency = "LOW"
            elif dominant_archetype == WhaleArchetypeEnum.FADED_CONTRARIAN:
                recommended_action = RecommendedActionEnum.FADE_CONTRARIAN
                risk_tier = RiskTierEnum.HIGH
                urgency = "MEDIUM"
            elif avg_price >= 0.88:
                recommended_action = RecommendedActionEnum.WAIT_PULLBACK
                risk_tier = RiskTierEnum.HIGH
                urgency = "LOW"
            elif dominant_outcome == "YES":
                recommended_action = RecommendedActionEnum.BUY_YES
                risk_tier = RiskTierEnum.LOW if (confidence_score >= 80 and not has_conflict) else RiskTierEnum.MEDIUM
                urgency = "CRITICAL" if (confidence_score >= 85 and total_volume > 10000) else ("HIGH" if confidence_score >= 70 else "MEDIUM")
            else:
                recommended_action = RecommendedActionEnum.BUY_NO
                risk_tier = RiskTierEnum.LOW if (confidence_score >= 80 and not has_conflict) else RiskTierEnum.MEDIUM
                urgency = "CRITICAL" if (confidence_score >= 85 and total_volume > 10000) else ("HIGH" if confidence_score >= 70 else "MEDIUM")

            suggested_max_entry = min(0.92, round(avg_price + 0.05, 4))
            potential_roi = round(((1.0 - avg_price) / avg_price * 100), 1) if avg_price > 0 else 0.0

            # Sweet Spot Entry Zone Classification
            if avg_price >= 0.88:
                entry_zone = EntryZoneEnum.AVOID_LATE_FOMO
            elif avg_price > 0.75:
                entry_zone = EntryZoneEnum.LATE_OVERBOUGHT
            elif avg_price >= 0.35:
                entry_zone = EntryZoneEnum.OPTIMAL_SWEET_SPOT
            else:
                entry_zone = EntryZoneEnum.EARLY_SPECULATIVE

            actionable_decision = ActionableDecision(
                recommended_action=recommended_action,
                risk_tier=risk_tier,
                entry_zone=entry_zone,
                suggested_max_entry_price=suggested_max_entry,
                current_entry_price=round(avg_price, 4),
                potential_roi_percent=potential_roi,
                urgency=urgency,
            )


            # Generate structured AI rationale for Hermes LLM reasoning
            market_title = dominant_list[0].market_title or condition_id
            market_slug = dominant_list[0].market_slug

            conflict_str = (
                f" WARNING: {conflict_count} whale(s) entered opposite outcome."
                if has_conflict
                else " No conflicting whale positions detected."
            )
            sybil_str = " (Sybil cluster suspected: synchronized entries <3m)" if is_sybil_suspected else ""

            ai_rationale = (
                f"[{strength.value}] {whale_count} whale(s) ({dominant_archetype.value}) accumulated "
                f"${total_volume:,.2f} on {dominant_outcome} @ avg {avg_price:.3f}. "
                f"Avg win rate: {avg_win_rate * 100:.1f}%, Trend: {price_trend} (drift: {price_drift:+.3f}). "
                f"Action: {recommended_action.value} (Risk: {risk_tier.value}, Max safe entry: {suggested_max_entry:.3f}, Upside: +{potential_roi:.1f}%).{conflict_str}{sybil_str}"
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
                    actionable_signal=actionable_decision,
                    smart_money_breakdown=smart_money,
                    market_velocity=market_velocity,
                    ai_rationale=ai_rationale,
                    first_trade_at=first_trade,
                    last_trade_at=last_trade,
                )
            )

        # Sort signals by confidence score descending, then volume descending
        signals.sort(key=lambda s: (s.confidence_score, s.total_volume_usdc), reverse=True)
        final_signals = signals[:limit]
        await memory_cache.set(cache_key, final_signals, ttl=settings.CACHE_TTL_SECONDS)
        return final_signals

    async def get_portfolio_holdings_consensus(
        self,
        db: AsyncSession,
        min_whales: int = 1,
        limit: int = 30,
    ) -> list[MarketHoldingsConsensusResponse]:
        """Aggregate open portfolio positions across all tracked whales and compute YES vs NO battle consensus."""
        cache_key = f"signals:holdings:{min_whales}:{limit}"
        cached_result = await memory_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # 1. Fetch all active positions with size > 0 or cur_value > 0
        pos_query = (
            select(Position)
            .where(Position.condition_id.isnot(None), Position.cur_value > 0.0)
            .order_by(Position.updated_at.desc())
        )

        pos_res = await db.execute(pos_query)
        positions = pos_res.scalars().all()

        # 2. Fetch wallet metadata & snapshots (1 row per wallet)
        wallets_res = await db.execute(select(Wallet))
        wallets_map = {w.address: w for w in wallets_res.scalars().all()}

        snaps_res = await db.execute(select(Snapshot))
        snaps_map = {s.wallet_address: s for s in snaps_res.scalars().all()}


        # 3. Group positions by condition_id
        market_groups: dict[str, list[Position]] = defaultdict(list)
        for p in positions:
            market_groups[p.condition_id].append(p)

        results: list[MarketHoldingsConsensusResponse] = []

        for condition_id, pos_list in market_groups.items():
            market_title = pos_list[0].market_title or condition_id
            market_slug = pos_list[0].market_slug

            # Group by outcome (YES vs NO vs other)
            outcome_whales: dict[str, list[Position]] = defaultdict(list)
            unique_whale_addresses = set()

            for p in pos_list:
                norm_outcome = (p.outcome or "YES").strip().upper()
                outcome_whales[norm_outcome].append(p)
                unique_whale_addresses.add(p.wallet_address)

            total_whales_count = len(unique_whale_addresses)
            if total_whales_count < min_whales:
                continue

            # Build breakdown helper
            def _build_outcome_breakdown(outcome_str: str) -> OutcomeHoldingsBreakdown:
                plist = outcome_whales.get(outcome_str, [])
                w_infos: list[WhaleHoldingInfo] = []
                total_val = 0.0
                total_shares = 0.0
                total_pnl = 0.0
                weighted_entry_sum = 0.0
                current_p = 0.0

                for pos in plist:
                    w = wallets_map.get(pos.wallet_address)
                    sn = snaps_map.get(pos.wallet_address)
                    w_rate = sn.win_rate if sn else 0.50
                    w_vol = sn.total_volume_usdc if sn else pos.cur_value
                    w_trades = sn.total_trades_count if sn else 1

                    arch, tier = self._classify_whale_archetype(
                        win_rate=w_rate, size_usdc=w_vol, trade_count=w_trades
                    )

                    val = float(pos.cur_value or 0.0)
                    sz = float(pos.size or 0.0)
                    entry_p = float(pos.avg_price or 0.0)
                    cur_p = float(pos.current_price or 0.0)
                    pnl = float(pos.unrealized_pnl or 0.0)

                    total_val += val
                    total_shares += sz
                    total_pnl += pnl
                    weighted_entry_sum += (entry_p * val)
                    if cur_p > 0:
                        current_p = cur_p

                    w_infos.append(
                        WhaleHoldingInfo(
                            address=pos.wallet_address,
                            label=w.label if w else None,
                            size=round(sz, 2),
                            cur_value=round(val, 2),
                            avg_price=round(entry_p, 4),
                            current_price=round(cur_p, 4),
                            unrealized_pnl=round(pnl, 2),
                            win_rate=round(w_rate, 4),
                            archetype=arch.value,
                            conviction_tier=tier.value,
                        )
                    )

                avg_entry = (weighted_entry_sum / total_val) if total_val > 0 else 0.0
                # Sort whales in breakdown by position value descending
                w_infos.sort(key=lambda x: x.cur_value, reverse=True)

                return OutcomeHoldingsBreakdown(
                    outcome=outcome_str,
                    whale_count=len(plist),
                    total_value_usdc=round(total_val, 2),
                    total_shares_size=round(total_shares, 2),
                    average_entry_price=round(avg_entry, 4),
                    current_price=round(current_p, 4),
                    total_unrealized_pnl=round(total_pnl, 2),
                    whales=w_infos,
                )

            yes_breakdown = _build_outcome_breakdown("YES")
            no_breakdown = _build_outcome_breakdown("NO")

            total_portfolio_usdc = round(yes_breakdown.total_value_usdc + no_breakdown.total_value_usdc, 2)
            if total_portfolio_usdc <= 0:
                total_portfolio_usdc = sum(float(p.cur_value or 0.0) for p in pos_list)

            # Dominance & Verdict calculation
            if yes_breakdown.total_value_usdc >= no_breakdown.total_value_usdc:
                dominant_outcome = "YES"
                dom_pct = (yes_breakdown.total_value_usdc / total_portfolio_usdc * 100.0) if total_portfolio_usdc > 0 else 50.0
            else:
                dominant_outcome = "NO"
                dom_pct = (no_breakdown.total_value_usdc / total_portfolio_usdc * 100.0) if total_portfolio_usdc > 0 else 50.0

            # Determine Verdict
            if yes_breakdown.whale_count >= 2 and no_breakdown.whale_count == 0:
                verdict = "STRONG_YES_CONVERGENCE"
            elif no_breakdown.whale_count >= 2 and yes_breakdown.whale_count == 0:
                verdict = "STRONG_NO_CONVERGENCE"
            elif yes_breakdown.whale_count >= 1 and no_breakdown.whale_count >= 1:
                verdict = "WHALE_BATTLE_CONFLICT"
            elif yes_breakdown.whale_count == 1 and no_breakdown.whale_count == 0:
                verdict = "SINGLE_WHALE_YES"
            else:
                verdict = "SINGLE_WHALE_NO"

            # Confidence score (0 to 100)
            base_score = 40.0
            whale_multiplier = min(40.0, total_whales_count * 12.0)
            dom_weight = (dom_pct / 100.0) * 20.0
            conflict_penalty = 25.0 if verdict == "WHALE_BATTLE_CONFLICT" else 0.0
            conf_score = max(10.0, min(99.0, round(base_score + whale_multiplier + dom_weight - conflict_penalty, 1)))

            # AI Summary
            if verdict == "WHALE_BATTLE_CONFLICT":
                ai_summary = (
                    f"⚔️ Whale Battle Conflict: {yes_breakdown.whale_count} whale(s) hold YES (${yes_breakdown.total_value_usdc:,.2f}) "
                    f"versus {no_breakdown.whale_count} whale(s) holding NO (${no_breakdown.total_value_usdc:,.2f}). Market is heavily contested."
                )
            elif dominant_outcome == "YES":
                ai_summary = (
                    f"🏆 Strong YES Consensus: {yes_breakdown.whale_count} tracked whale(s) hold YES positions totaling "
                    f"${yes_breakdown.total_value_usdc:,.2f} USDC ({dom_pct:.1f}% dominance, avg entry: {yes_breakdown.average_entry_price:.3f})."
                )
            else:
                ai_summary = (
                    f"🛡️ Strong NO Consensus: {no_breakdown.whale_count} tracked whale(s) hold NO positions totaling "
                    f"${no_breakdown.total_value_usdc:,.2f} USDC ({dom_pct:.1f}% dominance, avg entry: {no_breakdown.average_entry_price:.3f})."
                )

            dominant_avg_price = yes_breakdown.average_entry_price if dominant_outcome == "YES" else no_breakdown.average_entry_price
            holdings_roi = round(((1.0 - dominant_avg_price) / dominant_avg_price * 100), 1) if dominant_avg_price > 0 else 0.0
            if dominant_avg_price >= 0.88:
                holdings_entry_zone = EntryZoneEnum.AVOID_LATE_FOMO
            elif dominant_avg_price > 0.75:
                holdings_entry_zone = EntryZoneEnum.LATE_OVERBOUGHT
            elif dominant_avg_price >= 0.35:
                holdings_entry_zone = EntryZoneEnum.OPTIMAL_SWEET_SPOT
            else:
                holdings_entry_zone = EntryZoneEnum.EARLY_SPECULATIVE

            results.append(
                MarketHoldingsConsensusResponse(
                    condition_id=condition_id,
                    market_title=market_title,
                    market_slug=market_slug,
                    total_whales_count=total_whales_count,
                    total_portfolio_usdc=total_portfolio_usdc,
                    dominant_outcome=dominant_outcome,
                    dominance_percentage=round(dom_pct, 1),
                    verdict=verdict,
                    entry_zone=holdings_entry_zone,
                    potential_roi_percent=holdings_roi,
                    confidence_score=conf_score,
                    yes_side=yes_breakdown,
                    no_side=no_breakdown,
                    ai_summary=ai_summary,
                )
            )


        # Sort: markets with more whales first, then highest portfolio value
        results.sort(key=lambda x: (x.total_whales_count, x.total_portfolio_usdc), reverse=True)
        final_results = results[:limit]
        await memory_cache.set(cache_key, final_results, ttl=settings.CACHE_TTL_SECONDS)
        return final_results


consensus_service = ConsensusService()

