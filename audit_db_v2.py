import asyncio
from scraper.core.db import get_companies_col

async def audit():
    col = get_companies_col()
    cursor = col.find({}, {"symbol": 1, "fundametrics_response": 1})
    
    missing_fr = []
    missing_pe = []
    missing_roe = []
    missing_marketcap = []
    
    async for doc in cursor:
        sym = doc.get("symbol")
        fr = doc.get("fundametrics_response")
        if not fr:
            missing_fr.append(sym)
            continue
            
        metrics = fr.get("metrics", {})
        v = metrics.get("values", {})
        r = metrics.get("ratios", {})
        
        # Comprehensive check
        has_pe = any(k in r or k in v for k in ["fundametrics_pe_ratio", "price_to_earnings", "pe_ratio"])
        has_roe = any(k in r or k in v for k in ["fundametrics_return_on_equity", "return_on_equity", "roe"])
        has_mcap = any(k in v or k in r for k in ["market_cap", "fundametrics_market_cap"])
        
        if not has_pe: missing_pe.append(sym)
        if not has_roe: missing_roe.append(sym)
        if not has_mcap: missing_marketcap.append(sym)
            
    print(f"Missing FR ({len(missing_fr)}): {missing_fr[:10]}")
    print(f"Missing PE ({len(missing_pe)}): {missing_pe[:10]}")
    print(f"Missing ROE ({len(missing_roe)}): {missing_roe[:10]}")
    print(f"Missing Mcap ({len(missing_marketcap)}): {missing_marketcap[:10]}")

if __name__ == "__main__":
    asyncio.run(audit())
