import asyncio
from scraper.core.db import get_companies_col

async def d():
    doc = await get_companies_col().find_one({'symbol': 'AARTIIND'})
    fr = doc.get('fundametrics_response', {})
    m = fr.get('metrics', {})
    r = m.get('ratios', {})
    v = m.get('values', {})
    
    print("MATCHING KEYS FOR ROE:")
    for k in list(r.keys()) + list(v.keys()):
        if 'equity' in k.lower() or 'roe' in k.lower():
            val = r.get(k) or v.get(k)
            print(f"{k}: {val}")

if __name__ == "__main__":
    asyncio.run(d())
