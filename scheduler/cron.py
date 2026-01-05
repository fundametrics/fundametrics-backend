import asyncio
import os
import sys
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.utils.logger import setup_logging, get_logger
from db.manager import init_db, db_manager
from scheduler.engine import ScraperEngine

load_dotenv()
log = get_logger(__name__)

def load_symbols(file_path: str) -> list:
    """Loads stock symbols from a text file."""
    if not os.path.exists(file_path):
        log.error(f"Symbols file not found: {file_path}")
        return []
    
    symbols = []
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                symbols.append(line)
    return symbols

async def daily_job():
    """The main task executed by the scheduler."""
    log.info("Starting scheduled daily scrape job")
    
    # Load symbols
    symbols_file = os.getenv("SYMBOLS_FILE", "./config/stock_symbols.txt")
    symbols = load_symbols(symbols_file)
    
    if not symbols:
        log.warning("No symbols to scrape. Job exiting.")
        return

    # Initialize Engine with settings
    # For now, we'll hardcode some or pull from env to keep it simple, 
    # but in a real app we'd load the yaml here.
    max_concurrent = int(os.getenv("MAX_CONCURRENCY", 5))
    engine = ScraperEngine(max_concurrency=max_concurrent)
    
    try:
        await engine.run_bulk_scrape(symbols)
    except Exception as e:
        log.exception(f"Critical failure in daily_job: {e}")
    finally:
        log.info("Scheduled daily scrape job completed")

async def main():
    # 1. Setup Logging
    setup_logging()
    log.info("=== Fundametrics Scraper Scheduler Starting ===")

    # 2. Initialize Database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Fallback to building from env vars if needed, but DATABASE_URL is preferred
        log.critical("DATABASE_URL not set in .env")
        return

    init_db(db_url)
    
    # Check connection
    if not await db_manager.check_connection():
        log.critical("Could not connect to database. Scheduler exiting.")
        return

    # 3. Setup Scheduler
    scheduler = AsyncIOScheduler()
    
    # Get schedule from env or default to 6 PM IST
    hour = int(os.getenv("SCRAPE_HOUR", 18))
    minute = int(os.getenv("SCRAPE_MINUTE", 0))
    
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=hour, minute=minute, timezone="Asia/Kolkata"),
        name="daily_stock_scrape"
    )
    
    scheduler.start()
    log.info(f"Scheduler started. Daily job scheduled for {hour:02d}:{minute:02d} IST.")

    # Optional: Run immediately if flag is set
    if "--now" in sys.argv:
        log.info("Running job immediately (--now flag detected)")
        await daily_job()

    # Keep the script running
    try:
        while True:
            await asyncio.sleep(100)
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler shutting down...")
        if db_manager:
            await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
