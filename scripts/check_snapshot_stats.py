import asyncio
from scraper.core.db import get_companies_col

async def check_stats():
    col = get_companies_col()
    total = await col.count_documents({})
    with_snapshot = await col.count_documents({"snapshot": {"$exists": True}})
    with_market_cap = await col.count_documents({"snapshot.marketCap": {"$gt": 0}})
    
    print(f"Total Companies: {total}")
    print(f"With Snapshot: {with_snapshot}")
    print(f"With Market Cap in Snapshot: {with_market_cap}")

if __name__ == "__main__":
    asyncio.run(check_stats())
