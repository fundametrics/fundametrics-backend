"""
Quick script to check registry count and autopilot status
"""
import asyncio
from scraper.core.db import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_status():
    db = get_db()
    
    # Check registry count
    registry_col = db["companies_registry"]
    registry_count = await registry_col.count_documents({})
    logger.info(f"📊 Companies Registry Count: {registry_count}")
    
    # Check analyzed companies count
    companies_col = db["companies"]
    analyzed_count = await companies_col.count_documents({})
    logger.info(f"📊 Analyzed Companies Count: {analyzed_count}")
    
    # Check how many are pending
    pending = registry_count - analyzed_count
    logger.info(f"⏳ Pending Analysis: {pending}")
    
    # Check recent ingestions (last 24 hours)
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    recent_count = await companies_col.count_documents({
        "ingested_at": {"$gte": yesterday.isoformat()}
    })
    logger.info(f"📈 Ingested in last 24h: {recent_count}")
    
    # Sample some problematic stocks
    problem_stocks = ["TATAMOTORS", "TMCV", "TMPV", "ZOMATO"]
    for symbol in problem_stocks:
        doc = await companies_col.find_one({"symbol": symbol})
        if doc:
            logger.info(f"✅ {symbol}: Data exists (ingested: {doc.get('ingested_at', 'unknown')})")
        else:
            logger.info(f"❌ {symbol}: NO DATA")

if __name__ == "__main__":
    asyncio.run(check_status())
