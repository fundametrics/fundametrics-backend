import asyncio
from scraper.core.db import get_companies_col

async def audit():
    col = get_companies_col()
    cursor = col.find({}, {"symbol": 1, "fundametrics_response": 1})
    
    missing_pe = []
    
    async for doc in cursor:
        sym = doc.get("symbol")
        fr = doc.get("fundametrics_response", {})
        if not fr:
            # print(f"{sym} has no fundametrics_response")
            missing_pe.append(sym)
            continue
            
        metrics = fr.get("metrics", {})
        v = metrics.get("values", {})
        r = metrics.get("ratios", {})
        
        has_pe = any(k in r or k in v for k in ["fundametrics_pe_ratio", "price_to_earnings", "pe_ratio"])
        
        if not has_pe:
            missing_pe.append(sym)
            # print(f"{sym} missing PE. Keys in Ratios: {list(r.keys())}")
            
    print(f"TOTAL MISSING PE: {len(missing_pe)}")
    print(f"SAMPLE MISSING: {missing_pe[:20]}")

if __name__ == "__main__":
    asyncio.run(audit())
