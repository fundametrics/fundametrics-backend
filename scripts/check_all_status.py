import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def main():
    db = get_db()
    
    # Check Registry
    registry_total = await db.companies_registry.count_documents({})
    registry_verified = await db.companies_registry.count_documents({"status": "verified"})
    
    # Check Ingested Data
    data_total = await db.companies.count_documents({})
    
    print(f"--- Global Status ---")
    print(f"Total Companies in Registry: {registry_total}")
    print(f"Companies marked 'verified' in Registry: {registry_verified}")
    print(f"Companies with full data in MongoDB: {data_total}")
    
    # Check samples
    if data_total > 0:
        print("\n--- Samples Ingested ---")
        async for stock in db.companies.find({}, {"symbol": 1, "fundametrics_metrics": 1}).limit(10):
            symbol = stock.get("symbol")
            metrics = stock.get("fundametrics_metrics", [])
            has_price = any(m.get("metric_name") == "Current Price" for m in metrics)
            print(f"Symbol: {symbol:10} | Has Price Metric: {has_price}")

if __name__ == "__main__":
    asyncio.run(main())
