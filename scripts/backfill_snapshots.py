import asyncio
import logging
from scraper.core.db import get_companies_col, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_snapshots():
    col = get_companies_col()
    cursor = col.find({})
    
    total = await col.count_documents({})
    logger.info(f"🚀 Starting backfill for {total} companies...")
    
    count = 0
    updated = 0
    
    async for doc in cursor:
        count += 1
        symbol = doc.get("symbol")
        
        # Skip if already has a rich snapshot? 
        # Actually, let's refresh them all for consistency.
        
        fr = doc.get("fundametrics_response") or {}
        ui_metrics = fr.get("fundametrics_metrics") or []
        fr_comp = fr.get("company") or {}
        
        # Build metric map
        m_map = {}
        if isinstance(ui_metrics, list):
            m_map = {m.get("metric_name"): m.get("value") for m in ui_metrics if isinstance(m, dict) and m.get("metric_name")}
        
        # Emergency Fallback for MCAP/Price from deep metrics
        mcap = m_map.get("Market Cap") or m_map.get("Market_Cap")
        price = m_map.get("Current Price") or m_map.get("Price")
        
        if not mcap or not price:
            deep_metrics = fr.get("metrics", {}).get("values", [])
            if isinstance(deep_metrics, list):
                for m in deep_metrics:
                    if not mcap and m.get("metric") in ["Market Cap", "Market_Cap", "MCAP"]:
                        mcap = m.get("value")
                    if not price and m.get("metric") in ["Price", "Current Price"]:
                        price = m.get("value")

        # Build snapshot
        snapshot = {
            "symbol": symbol,
            "name": doc.get("name") or fr_comp.get("name") or symbol,
            "sector": doc.get("sector") or fr_comp.get("sector") or "General",
            "industry": doc.get("industry") or fr_comp.get("industry") or "General",
            "marketCap": mcap,
            "currentPrice": price,
            "pe": m_map.get("pe_ratio") or m_map.get("p/e_ratio") or m_map.get("PE Ratio"),
            "roe": m_map.get("roe") or m_map.get("return_on_equity") or m_map.get("ROE"),
            "roce": m_map.get("roce") or m_map.get("return_on_capital_employed") or m_map.get("ROCE"),
            "priority": doc.get("snapshot", {}).get("priority") or 0
        }
        
        # Also promote sector and name to root for faster filtering
        update_payload = {
            "snapshot": snapshot,
            "sector": snapshot["sector"],
            "name": snapshot["name"]
        }
        
        await col.update_one({"_id": doc["_id"]}, {"$set": update_payload})
        updated += 1
        
        if count % 100 == 0:
            logger.info(f"Processed {count}/{total}...")

    logger.info(f"✅ Backfill complete. Updated {updated} companies.")

if __name__ == "__main__":
    asyncio.run(backfill_snapshots())
