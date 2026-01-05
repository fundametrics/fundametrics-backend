import asyncio
from scraper.core.db import get_companies_col
from datetime import datetime

async def verify():
    col = get_companies_col()
    symbols = ["AARTIIND", "RELIANCE", "TATAMOTORS"]
    for sym in symbols:
        doc = await col.find_one({"symbol": sym})
        if not doc:
            print(f"{sym}: Not found in DB")
            continue
        
        fr = doc.get("fundametrics_response", {})
        metrics = fr.get("metrics", {}).get("values", {})
        ratios = fr.get("metrics", {}).get("ratios", {})
        
        pe = ratios.get("fundametrics_pe_ratio") or metrics.get("fundametrics_pe_ratio")
        roe = ratios.get("fundametrics_return_on_equity") or metrics.get("fundametrics_return_on_equity")
        
        print(f"{sym}:")
        print(f"  PE: {pe}")
        print(f"  ROE: {roe}")
        
        # Check source snapshot constants
        consts = fr.get("metadata", {}).get("constants", {})
        print(f"  Constants ROE: {consts.get('roe')}")

if __name__ == "__main__":
    asyncio.run(verify())
