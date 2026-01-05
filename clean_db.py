import asyncio
from scraper.core.db import get_companies_col

async def clean():
    col = get_companies_col()
    result = await col.delete_many({"symbol": {"$regex": "^--"}})
    print(f"Deleted {result.deleted_count} junk records.")

if __name__ == "__main__":
    asyncio.run(clean())
