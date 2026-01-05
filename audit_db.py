import asyncio
from scraper.core.db import get_companies_col

async def audit():
    col = get_companies_col()
    cursor = col.find({}, {"symbol": 1, "fundametrics_response.metrics": 1, "fundametrics_response.financials": 1})
    
    total = 0
    missing_fr = 0
    missing_metrics = 0
    missing_pe = 0
    missing_roe = 0
    
    async for doc in cursor:
        total += 1
        fr = doc.get("fundametrics_response")
        if not fr:
            missing_fr += 1
            continue
        
        metrics = fr.get("metrics", {})
        vals = metrics.get("values", {})
        ratios = metrics.get("ratios", {})
        
        # Check PE
        pe = ratios.get("fundametrics_pe_ratio") or ratios.get("price_to_earnings") or vals.get("fundametrics_pe_ratio")
        if not pe:
            missing_pe += 1
            
        # Check ROE
        roe = ratios.get("fundametrics_return_on_equity") or ratios.get("return_on_equity")
        if not roe:
            missing_roe += 1
            
    print(f"Total Companies: {total}")
    print(f"Missing fundametrics_response: {missing_fr}")
    print(f"Missing PE: {missing_pe}")
    print(f"Missing ROE: {missing_roe}")

if __name__ == "__main__":
    asyncio.run(audit())
