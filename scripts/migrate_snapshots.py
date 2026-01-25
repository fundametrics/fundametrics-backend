import asyncio
from scraper.core.db import get_companies_col, get_db
from scraper.core.ingestion import _build_snapshot
from scraper.core.mongo_repository import MongoRepository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    col = get_companies_col()
    repo = MongoRepository(get_db())
    
    cursor = col.find({})
    count = 0
    
    async for doc in cursor:
        symbol = doc.get("symbol")
        fr = doc.get("fundametrics_response")
        
        if not symbol or not fr:
            continue
            
        snapshot = _build_snapshot(symbol, fr)
        await col.update_one(
            {"_id": doc["_id"]},
            {"$set": {"snapshot": snapshot}}
        )
        count += 1
        if count % 10 == 0:
            logger.info(f"Migrated {count} companies...")
            
    logger.info(f"Done! Migrated {count} companies.")

if __name__ == "__main__":
    asyncio.run(migrate())
