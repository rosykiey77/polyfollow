import asyncio
import datetime
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.services.tracker import tracker_service


class BackgroundPoller:
    def __init__(self):
        self.is_running: bool = False
        self.last_run_time: datetime.datetime | None = None
        self.total_runs: int = 0
        self.error_count: int = 0
    async def _deferred_initial_discovery(self):
        """Run initial whale discovery in background 60 seconds after boot to prevent CPU spike on start."""
        try:
            await asyncio.sleep(60)
            if not self.is_running:
                return
            logger.info("Running deferred initial whale discovery (60s post-boot)...")
            async with async_session_factory() as session:
                await tracker_service.discover_and_register_whales(session)
        except Exception as err:
            logger.warning("Deferred initial discovery error: %s", str(err))

    async def _poller_loop(self):
        logger.info(
            "Polymarket Background Poller started (interval: %ds, auto-discovery: %s)",
            settings.POLLING_INTERVAL_SECONDS,
            settings.ENABLE_AUTO_DISCOVERY,
        )
        self.is_running = True

        # Initial seed on startup (lightweight local check)
        try:
            async with async_session_factory() as session:
                await tracker_service.seed_initial_wallets(session)
                if settings.ENABLE_AUTO_DISCOVERY:
                    asyncio.create_task(self._deferred_initial_discovery())
        except Exception as startup_err:
            logger.warning("Error during initial poller startup: %s", str(startup_err))


        while self.is_running:
            try:
                self.last_run_time = datetime.datetime.now(datetime.timezone.utc)
                async with async_session_factory() as session:
                    # Periodically run whale discovery
                    if settings.ENABLE_AUTO_DISCOVERY and (self.total_runs > 0) and (self.total_runs % settings.AUTO_DISCOVERY_INTERVAL_RUNS == 0):
                        try:
                            await tracker_service.discover_and_register_whales(session)
                        except Exception as disc_err:
                            logger.warning("Error during periodic whale discovery: %s", str(disc_err))

                    sync_results = await tracker_service.sync_all_active_wallets(session)
                    self.total_runs += 1
                    total_new_trades = sum(r.get("new_trades_detected", 0) for r in sync_results)
                    total_positions = sum(r.get("positions_synced", 0) for r in sync_results)
                    logger.info(
                        "Poller cycle #%d complete: %d active wallets synced, %d total positions, %d new trades detected.",
                        self.total_runs,
                        len(sync_results),
                        total_positions,
                        total_new_trades,
                    )

                    # If new trades detected or high score alerts configured, evaluate signals for outbound dispatch
                    if total_new_trades > 0 and (settings.HERMES_WEBHOOK_URL or settings.TELEGRAM_BOT_TOKEN):
                        try:
                            from app.services.consensus import consensus_service
                            from app.services.webhook import webhook_service

                            signals = await consensus_service.get_consensus_signals(
                                db=session,
                                timeframe="6h",
                                min_score=settings.MIN_ALERT_CONFIDENCE_SCORE,
                                min_whales=1,
                                limit=5,
                            )
                            for sig in signals:
                                await webhook_service.dispatch_signal_alert(sig.model_dump())
                        except Exception as alert_err:
                            logger.warning("Error evaluating consensus signals for webhook dispatch: %s", str(alert_err))
            except asyncio.CancelledError:
                logger.info("Background Poller received cancellation signal.")
                break
            except Exception as exc:
                self.error_count += 1
                logger.error("Error in background poller iteration: %s", str(exc), exc_info=True)

            try:
                await asyncio.sleep(settings.POLLING_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

        self.is_running = False
        logger.info("Polymarket Background Poller stopped.")

    def start(self):
        if not settings.ENABLE_BACKGROUND_POLLER:
            logger.info("Background poller is disabled via configuration.")
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poller_loop())

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


poller = BackgroundPoller()
