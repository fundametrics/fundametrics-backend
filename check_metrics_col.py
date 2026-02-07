import asyncio
from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db, get_metrics_col
from dotenv import load_dotenv

async def main():
    load_dotenv()
    col = get_metrics_col()
    symbol = "RELIANCE"
    cursor = col.find({"symbol": symbol})
    metrics = [doc async for doc in cursor]
    print(f"Metrics for {symbol}:")
    for m in metrics:
        print(f"  {m.get('metric_name') or m.get('metric')}: {m.get('value')}")

if __name__ == "__main__":
    asyncio.run(main())
