import asyncio
from scraper.core.db import get_companies_col
import json

async def debug():
    col = get_companies_col()
    doc = await col.find_one({"symbol": "AARTIIND"})
    fr = doc.get("fundametrics_response", {})
    r_table = fr.get("financials", {}).get("ratios_table", {})
    
    print("AARTIIND Ratios Table Periods:")
    for p in sorted(r_table.keys(), reverse=True):
        print(f"{p}: {list(r_table[p].keys())}")
        if 'roe' in r_table[p]:
            print(f"  roe value: {r_table[p]['roe']}")
            
    print("\nTop Constants (metadata.constants):")
    print(json.dumps(fr.get("metadata", {}).get("constants", {}), indent=2))

if __name__ == "__main__":
    asyncio.run(debug())
