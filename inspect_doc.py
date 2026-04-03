import asyncio
import logging
import os
from dotenv import load_dotenv
from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db

async def main():
    load_dotenv()
    repo = MongoRepository(get_db())
    symbol = "RELIANCE"
    doc = await repo.get_company(symbol)
    if not doc:
        print(f"No document found for {symbol}")
        return
    
    print(f"Top-level keys: {list(doc.keys())}")
    fr = doc.get("fundametrics_response", {})
    print(f"fundametrics_response keys: {list(fr.keys())}")
    
    # Check if metrics are anywhere else
    for k, v in doc.items():
        if "metric" in k.lower():
            print(f"Found metric-like key at top level: {k}")
            
    # Print the first few items of fundametrics_metrics if it exists
    if "fundametrics_metrics" in fr:
        print(f"fundametrics_metrics (first 5): {fr['fundametrics_metrics'][:5]}")
    elif "metrics" in fr:
        print(f"metrics keys: {list(fr['metrics'].keys())}")
    
    # Check snapshots
    print(f"Snapshot data: {doc.get('snapshot')}")

if __name__ == "__main__":
    asyncio.run(main())
