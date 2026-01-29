import asyncio
import logging
from typing import Dict, Any
from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db, get_companies_col
from scraper.core.ingestion import _build_snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_snapshots():
    db = get_db()
    repo = MongoRepository(db)
    companies_col = get_companies_col()
    
    cursor = companies_col.find({})
    count = 0
    updated = 0
    
    async for doc in cursor:
        count += 1
        symbol = doc.get("symbol")
        fr = doc.get("fundametrics_response")
        
        if not symbol or not fr:
            logger.warning(f"Skipping {doc.get('_id')} - missing symbol or response")
            continue
            
        try:
            # Re-build snapshot using the new hardened logic
            new_snapshot = _build_snapshot(symbol, fr)
            
            # Update the document
            await companies_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"snapshot": new_snapshot}}
            )
            updated += 1
            if updated % 50 == 0:
                logger.info(f"Updated {updated} snapshots...")
        except Exception as e:
            logger.error(f"Failed to update {symbol}: {e}")
            
    logger.info(f"Backfill complete. Processed {count} documents, updated {updated} snapshots.")

if __name__ == "__main__":
    asyncio.run(backfill_snapshots())
