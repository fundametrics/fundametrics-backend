import asyncio
import os
import sys
from scraper.core.db import get_companies_col
from scraper.core.ingestion import ingest_symbol
from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db

async def ingest_missing():
    print("🔎 Finding companies with missing data...")
    col = get_companies_col()
    repo = MongoRepository(get_db())
    
    # extensive check: companies that exist but have no metrics
    cursor = col.find({}, {'symbol': 1, 'fundametrics_response.metrics': 1})
    
    missing_symbols = []
    async for doc in cursor:
        symbol = doc.get('symbol')
        fr = doc.get('fundametrics_response', {})
        metrics = fr.get('metrics')
        if not metrics or (not metrics.get('values') and not metrics.get('ratios')):
            missing_symbols.append(symbol)
            
    print(f"📉 Found {len(missing_symbols)} companies with minimal/no data.")
    print(f"📋 List: {missing_symbols[:10]} ...")
    
    for i, symbol in enumerate(missing_symbols, 1):
        print(f"\n🔄 [{i}/{len(missing_symbols)}] Ingesting {symbol} ...")
        try:
            result = await ingest_symbol(symbol)
            
            # Simplified upsert logic (similar to bulk_ingest_nse.py)
            payload = result["payload"]
            company_data = payload.get("company", {})
            metadata = payload.get("metadata", {})
            
            # We want to preserve existing fields if possible, but for now we just overwrite with fresh data
            # to ensure consistency.
            cleaned_doc = {
                "symbol": result["symbol"],
                "name": company_data.get("name") or metadata.get("company_name") or result["symbol"],
                "sector": company_data.get("sector") or "Unknown",
                "industry": company_data.get("industry") or "Unknown",
                "profile": {
                    "about": company_data.get("about", ""),
                    "management": result.get("storage_payload", {}).get("fundametrics_response", {}).get("management", [])
                },
                "coverage": result["payload"].get("coverage"),
                "fundametrics_response": result.get("storage_payload", {}).get("fundametrics_response", {}),
                # "last_updated": ... (repo handles this)
            }
            
            await repo.upsert_company(symbol, cleaned_doc)
            print(f"✅ Success: {symbol}")
            
        except Exception as e:
            print(f"❌ Failed {symbol}: {e}")
            
        await asyncio.sleep(2) # rate limit

if __name__ == "__main__":
    asyncio.run(ingest_missing())
