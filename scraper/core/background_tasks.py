import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scraper.api.mongo_routes import refresh_index_prices, refresh_all_indices_constituents

logger = logging.getLogger(__name__)

class MarketDataRefresher:
    """
    Manages background tasks to keep market data fresh without blocking API calls.
    """
    _scheduler = None

    @classmethod
    async def start(cls):
        """Initialize and start the background scheduler."""
        if cls._scheduler and cls._scheduler.running:
            return

        cls._scheduler = AsyncIOScheduler()
        
        # 1. Refresh global index prices every 15 minutes (Ghost-Mode reduced frequency)
        cls._scheduler.add_job(
            refresh_index_prices,
            'interval',
            minutes=15,
            id='refresh_index_prices',
            replace_existing=True
        )

        # 2. Refresh core index constituents every 60 minutes
        cls._scheduler.add_job(
            refresh_all_indices_constituents,
            'interval',
            minutes=60,
            id='refresh_constituents',
            replace_existing=True
        )

        cls._scheduler.start()
        logger.info("🚀 Background Market Refresher started.")
        
        # Initial trigger (with slight delay to avoid boot burst)
        async def initial_load():
            await asyncio.sleep(5)
            await refresh_index_prices()
            await refresh_all_indices_constituents()
            
        asyncio.create_task(initial_load())

    @classmethod
    async def stop(cls):
        """Gracefully shut down the scheduler."""
        if cls._scheduler:
            cls._scheduler.shutdown()
            logger.info("🛑 Background Market Refresher stopped.")
