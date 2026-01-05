import asyncio
from scraper.core.db import get_db

async def check_registry():
    db = get_db()
    col = db["companies_registry"]
    count = await col.count_documents({})
    ola = await col.find_one({"symbol": "OLA"})
    
    print("-" * 50)
    print(f"Total Registry Count: {count}")
    print(f"OLA Record: {ola}")
    print("-" * 50)
    
    # List first 10 symbols
    cursor = col.find({}, {"symbol": 1}).limit(10)
    symbols = [doc["symbol"] async for doc in cursor]
    print(f"Sample Symbols: {symbols}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check_registry())
