import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def main():
    db = get_db()
    rel = await db.companies.find_one({"symbol": "RELIANCE"})
    if rel:
        print("RELIANCE Metric Names:")
        for m in rel.get("fundametrics_metrics", []):
            print(f" - {m.get('metric_name')}")
    else:
        print("RELIANCE not found")

if __name__ == "__main__":
    asyncio.run(main())
