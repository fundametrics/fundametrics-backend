import asyncio
import httpx
import csv
from io import StringIO
from pymongo import MongoClient
import logging
import os
import sys

# Standalone configuration
# Pull directly from source code if env missing
MONGO_URL = os.getenv("MONGO_URI", "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority")
NSE_MASTER_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RegistryUpdate")

async def update_registry():
    logger.info("🚀 Starting NSE Registry Update (Standalone)...")
    logger.info(f"Target DB: {MONGO_URL.split('@')[1] if '@' in MONGO_URL else 'Local'}")

    # 1. Fetch CSV
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.get(NSE_MASTER_URL, headers=headers)
            resp.raise_for_status()
            content = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch NSE CSV: {e}")
        return

    # 2. Parse CSV
    reader = csv.DictReader(StringIO(content))
    companies = []
    for row in reader:
        symbol = row.get('SYMBOL')
        company_name = row.get('NAME OF COMPANY')
        
        # EQUITY_L usually has ' INDUSTRY' or similar check
        # Let's clean headers first just in case
        
        if symbol:
            companies.append({
                "symbol": symbol.strip().upper(),
                "name": company_name.strip() if company_name else symbol.strip(),
                "exchange": "NSE"
            })
            
    logger.info(f"Fetched {len(companies)} companies from NSE.")

    # 3. Update MongoDB
    try:
        # Use sync MongoClient
        client = MongoClient(MONGO_URL)
        # Force database name 'fundametrics' from URI or explicitly
        db = client.get_database("fundametrics")
        col = db["companies_registry"]
        
        logger.info(f"Connected to DB: {db.name}")
        
        inserted = 0
        updated = 0
        
        # Batch size for bulk writes? Pymongo update_one is slow loop.
        # But 2600 is small.
        
        for co in companies:
            # We want to preserve 'is_analyzed' and other fields if they exist
            res = col.update_one(
                {"symbol": co["symbol"]},
                {"$set": {
                    "name": co["name"],
                    "exchange": "NSE",
                    "updated_at": "2026-01-08T00:00:00Z"
                }, "$setOnInsert": {"is_analyzed": False, "sector": "General"}},
                upsert=True
            )
            
            if res.upserted_id:
                inserted += 1
            else:
                updated += 1
                
        logger.info(f"✅ Registry Update Complete.")
        logger.info(f"   Inserted New: {inserted}")
        logger.info(f"   Updated Existing: {updated}")
        
        total = col.count_documents({})
        logger.info(f"   Total Companies in Registry: {total}")
        
        client.close()
        
    except Exception as e:
        logger.error(f"DB Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(update_registry())
