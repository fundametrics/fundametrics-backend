import asyncio
from scraper.core.db import get_companies_col

async def d():
    cursor = get_companies_col().find({}, {'symbol': 1})
    symbols = [doc.get('symbol') async for doc in cursor]
    symbols.sort()
    for s in symbols:
        print(f"'{s}'")

if __name__ == "__main__":
    asyncio.run(d())
