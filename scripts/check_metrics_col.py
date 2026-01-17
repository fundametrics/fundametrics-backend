import asyncio
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def main():
    db = get_db()
    symbol = "RELIANCE"
    print(f"Checking Metrics collection for {symbol}...")
    cursor = db.metrics.find({"symbol": symbol})
    count = 0
    async for doc in cursor:
        count += 1
        print(f" - {doc.get('metric_name')}: {doc.get('value')} ({doc.get('period')})")
    
    if count == 0:
        print("No documents found in 'metrics' collection for this symbol.")

if __name__ == "__main__":
    asyncio.run(main())
