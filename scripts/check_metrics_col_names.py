import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def main():
    db = get_db()
    symbol = "RELIANCE"
    names = await db.metrics.distinct("metric_name", {"symbol": symbol})
    print(f"Metric names for {symbol}:")
    for n in sorted(names):
        print(f" - {n}")

if __name__ == "__main__":
    asyncio.run(main())
