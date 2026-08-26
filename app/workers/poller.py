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
            "Polymarket Background Poller started (interval: %ds)",
            settings.POLLING_INTERVAL_SECONDS,
        )
        self.is_running = True
        while self.is_running:
            try:
                self.last_run_time = datetime.datetime.now(datetime.timezone.utc)
                async with async_session_factory() as session:
                    sync_results = await tracker_service.sync_all_active_wallets(session)
                    self.total_runs += 1
                    total_new_trades = sum(r.get("new_trades_detected", 0) for r in sync_results)
                    if total_new_trades > 0:
                        logger.info(
                            "Poller iteration complete: %d wallets synced, %d new trades detected!",
                            len(sync_results),
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
