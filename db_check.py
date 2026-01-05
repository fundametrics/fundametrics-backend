import asyncio
from scraper.core.db import get_companies_col

async def main():
    col = get_companies_col()
    count = await col.count_documents({})
    print(f"Total Companies: {count}")
    
    first = await col.find_one({}, {"symbol": 1, "name": 1})
    print(f"First Company: {first}")

if __name__ == "__main__":
    asyncio.run(main())
