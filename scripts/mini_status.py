import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def main():
    db = get_db()
    reg = await db.companies_registry.count_documents({})
    ver = await db.companies_registry.count_documents({"status": "verified"})
    dat = await db.companies.count_documents({})
    rel = await db.companies.find_one({"symbol": "RELIANCE"})
    rel_p = any(m.get("metric_name") == "Current Price" for m in (rel.get("fundametrics_metrics", []) if rel else [])) if rel else "N/A"
    
    print(f"REGISTRY_TOTAL: {reg}")
    print(f"REGISTRY_VERIFIED: {ver}")
    print(f"DATA_SAMPLES: {dat}")
    print(f"RELIANCE_HAS_PRICE: {rel_p}")
    
    # Check another one
    sbin = await db.companies.find_one({"symbol": "SBIN"})
    sbin_p = any(m.get("metric_name") == "Current Price" for m in (sbin.get("fundametrics_metrics", []) if sbin else [])) if sbin else "N/A"
    print(f"SBIN_HAS_PRICE: {sbin_p}")

if __name__ == "__main__":
    asyncio.run(main())
