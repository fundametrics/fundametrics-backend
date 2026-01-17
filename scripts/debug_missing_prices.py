import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scraper.core.db import get_db

async def check():
    db = get_db()
    symbols = ["TCS", "INFY", "HDFCBANK", "SBIN", "RELIANCE"]
    print(f"{'Symbol':<10} | {'Price in Doc':<15} | {'Price in Blob':<15} | {'Price in Metrics':<15}")
    print("-" * 65)
    
    for s in symbols:
        doc = await db.companies.find_one({"symbol": s})
        if not doc:
            print(f"{s:<10} | NOT FOUND")
            continue
            
        p_doc = doc.get("price", {}).get("value")
        
        fr = doc.get("fundametrics_response", {})
        m_vals = fr.get("metrics", {}).get("values", {})
        p_blob = m_vals.get("Current Price", {}).get("value") if isinstance(m_vals.get("Current Price"), dict) else m_vals.get("Current Price")
        if not p_blob:
             p_blob = m_vals.get("fundametrics_current_price", {}).get("value") if isinstance(m_vals.get("fundametrics_current_price"), dict) else m_vals.get("fundametrics_current_price")

        m_doc = await db.metrics.find_one({"symbol": s, "metric_name": {"$in": ["Current Price", "fundametrics_current_price"]}})
        p_metric = m_doc.get("value") if m_doc else None
        
        print(f"{s:<10} | {str(p_doc):<15} | {str(p_blob):<15} | {str(p_metric):<15}")

if __name__ == "__main__":
    asyncio.run(check())
