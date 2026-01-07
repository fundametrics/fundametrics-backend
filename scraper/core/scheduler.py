
import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scraper.core.db import get_db, get_companies_col
from scraper.core.ingestion import ingest_symbol
from scraper.api.registry_routes import ingestion_locks, MAX_ANALYSES_PER_DAY, daily_counter

logger = logging.getLogger(__name__)

# Single scheduler instance
scheduler = AsyncIOScheduler()

async def auto_ingest_job():
    """
    Autopilot: Finds a company that needs data and ingests it.
    Run system: 1 company every 30 minutes to stay safe.
    """
    try:
        if len(ingestion_locks) > 0:
            logger.info("⚠️ Autopilot skipped: Ingestion queue busy")
            return

        db = get_db()
        registry_col = db["companies_registry"]
        companies_col = db["companies"]

        # 1. Get already analyzed symbols
        analyzed_cursor = companies_col.find({}, {"symbol": 1, "_id": 0})
        analyzed_symbols = {doc["symbol"] async for doc in analyzed_cursor}

        # 2. Find a candidate from registry that is NOT analyzed
        # We limit to 1 to pick just the next one
        # Optimization: In real prod, use $nin query, but for <5000 docs python set diff is fine/safer
        # to avoid massive scan if index missed.
        
        # Let's try to find high priority ones first (Nifty 50/500 logic is implicit if registry is sorted)
        # For now, just find ANY missing one.
        candidate_cursor = registry_col.find(
            {"symbol": {"$nin": list(analyzed_symbols)}},
            {"symbol": 1}
        ).limit(1)
        
        candidates = await candidate_cursor.to_list(length=1)
        
        if not candidates:
            logger.info("✅ Autopilot: All registry companies are analyzed! Good job.")
            return

        target_symbol = candidates[0]['symbol']
        
        # 3. Trigger Ingestion
        logger.info(f"🤖 Autopilot triggering ingestion for: {target_symbol}")
        
        # Add to lock to prevent double processing
        ingestion_locks.add(target_symbol)
        
        try:
            # We bypass daily limits for autopilot (it's "Admin" level)
            result = await ingest_symbol(target_symbol)
            logger.info(f"✅ Autopilot success: {target_symbol}")
        except Exception as e:
            logger.error(f"❌ Autopilot failed for {target_symbol}: {e}")
        finally:
            if target_symbol in ingestion_locks:
                ingestion_locks.remove(target_symbol)

    except Exception as e:
        logger.error(f"❌ Autopilot job crashed: {e}")

def start_scheduler():
    """Start the background scheduler"""
    if not scheduler.running:
        # Run every 5 minutes = ~288 companies/day (Safe Target: 300)
        scheduler.add_job(
            auto_ingest_job, 
            IntervalTrigger(minutes=5), 
            id="auto_ingest", 
            replace_existing=True
        )
        scheduler.start()
        logger.info("🚀 Autopilot Scheduler started (Interval: 5 mins - Target: ~300/day)")
