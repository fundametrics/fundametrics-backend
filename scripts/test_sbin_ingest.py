import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.ingestion import ingest_symbol
from scraper.core.db import get_db

async def main():
    symbol = "SBIN"
    print(f"Ingesting {symbol} with new logic...")
    ingest_result = await ingest_symbol(symbol)
    
    result = ingest_result["payload"]
    storage_payload = ingest_result["storage_payload"]
    
    db = get_db()
    
    # Save to MongoDB
    await db.companies.update_one(
        {"symbol": symbol},
        {
            "$set": {
                "symbol": symbol,
                "fundametrics_response": result,
                "storage_payload": storage_payload,
                "updated_at": "now_test"
            }
        },
        upsert=True
    )
    
    # Verify price in result
    metrics = result.get("metrics", {}).get("values", {})
    has_price = "Current Price" in metrics or "fundametrics_current_price" in metrics
    print(f"Ingestion complete for {symbol}. Has Price in metrics: {has_price}")
    if has_price:
        p = metrics.get("Current Price") or metrics.get("fundametrics_current_price")
        print(f"Price data: {p}")

if __name__ == "__main__":
    asyncio.run(main())
