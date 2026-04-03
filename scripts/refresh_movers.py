import asyncio
import logging
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.db import get_db
from scraper.core.mongo_repository import MongoRepository
from scraper.core.market_facts_engine import MarketFactsEngine
from scraper.core.fetcher import Fetcher
from scraper.core.rate_limiters import yahoo_limiter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def refresh_top_stocks():
    db = get_db()
    repo = MongoRepository(db)
    fetcher = Fetcher(rate_limiter=yahoo_limiter)
    engine = MarketFactsEngine(fetcher=fetcher)
    
    # Symbols to refresh (Top Nifty 50 staples that usually appear in the tied lists)
    symbols = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", 
        "ICICIBANK", "ITC", "BHARTIARTL", "SBIN", "LICI"
    ]
    
    logger.info(f"Refreshing top {len(symbols)} stocks to break ties...")
    
    # 1. Fetch live prices (this will use the new derived movement logic)
    prices = await engine.fetch_batch_prices(symbols)
    
    # 2. Update snapshots in database
    for symbol, data in prices.items():
        logger.info(f"Updating {symbol}: {data.get('change_percent', 0):.2f}%")
        
        # Update just the snapshot part
        await repo._companies.update_one(
            {"symbol": symbol},
            {"$set": {
                "snapshot.currentPrice": data.get("price"),
                "snapshot.changePercent": data.get("change_percent"),
                "snapshot.updatedAt": data.get("timestamp")
            }}
        )
        
    logger.info("Movers refresh complete.")
    await fetcher.close()

if __name__ == "__main__":
    asyncio.run(refresh_top_stocks())
