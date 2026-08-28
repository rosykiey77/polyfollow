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
        self._task: asyncio.Task | None = None

    async def _poller_loop(self):
        logger.info(
            "Polymarket Background Poller started (interval: %ds, auto-discovery: %s)",
            settings.POLLING_INTERVAL_SECONDS,
            settings.ENABLE_AUTO_DISCOVERY,
        )
        self.is_running = True

        # Initial seed & discovery on startup
        try:
            async with async_session_factory() as session:
                await tracker_service.seed_initial_wallets(session)
                if settings.ENABLE_AUTO_DISCOVERY:
                    await tracker_service.discover_and_register_whales(session)
        except Exception as startup_err:
            logger.warning("Error during initial poller startup discovery: %s", str(startup_err))

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
