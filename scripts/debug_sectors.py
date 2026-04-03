import asyncio
from scraper.core.db import get_db, get_companies_col

async def check_sectors():
    db = get_db()
    col = get_companies_col()
    sectors = await col.distinct("sector")
    print("Available Sectors in DB:")
    for s in sectors:
        print(f"- '{s}'")

if __name__ == "__main__":
    asyncio.run(check_sectors())
