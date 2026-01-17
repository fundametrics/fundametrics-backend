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
        print(f"RELIANCE Keys: {list(rel.keys())}")
        if "fundametrics_response" in rel:
            fr = rel["fundametrics_response"]
            print(f"FR Keys: {list(fr.keys())}")
            if "metrics" in fr:
                m = fr["metrics"]
                print(f"Metrics Keys: {list(m.keys())}")
                if "values" in m:
                    print(f"Values Keys (sample): {list(m['values'].keys())[:5]}")
    else:
        print("RELIANCE not found")

if __name__ == "__main__":
    asyncio.run(main())
