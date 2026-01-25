import logging
import asyncio
import random
from datetime import datetime
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
        
        # 1. Refresh global index prices every 30 minutes (Ghost-Mode reduced frequency)
        cls._scheduler.add_job(
            refresh_index_prices,
            'interval',
            minutes=30,
            id='refresh_index_prices',
            replace_existing=True
        )

        # 2. Refresh core index constituents every 4 hours
        cls._scheduler.add_job(
            refresh_all_indices_constituents,
            'interval',
            hours=4,
            id='refresh_constituents',
            replace_existing=True
        )

        cls._scheduler.start()
        logger.info("🚀 Background Market Refresher started.")
        
        # Cold-Boot Isolation (Phase 12)
        # Record start time to prevent risky refreshes in the first 5 mins
        cls.boot_time = datetime.now()

        # Initial trigger (Ghost-Mode: Randomized boot delay to avoid burst detection)
        # We wait 30-300 seconds before starting first fetch after a deploy.
        async def initial_load():
            from scraper.api.mongo_routes import seed_market_data
            
            # 1. Seed immediately from DB (instant data for users)
            await seed_market_data()
            
            # 2. Wait randomized delay before first network hit
            boot_delay = random.randint(30, 300)
            logger.info(f"🕐 Ghost-Boot: Delaying first network hit by {boot_delay}s...")
            await asyncio.sleep(boot_delay)
            
            await refresh_index_prices()
            await refresh_all_indices_constituents()
            
        asyncio.create_task(initial_load())

    @classmethod
    async def stop(cls):
        """Gracefully shut down the scheduler."""
        if cls._scheduler:
            cls._scheduler.shutdown()
            logger.info("🛑 Background Market Refresher stopped.")
