"""
Bulk Ingestion Script – NSE Companies
Safe for MongoDB Free Tier (Restartable)
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db
from scraper.core.ingestion import ingest_symbol
from scraper.utils.logger import setup_logging

setup_logging()

NSE_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","INFY","ICICIBANK","SBIN","ITC","LT",
    "HINDUNILVR","BHARTIARTL","KOTAKBANK","AXISBANK","ASIANPAINT",
    "HCLTECH","BAJFINANCE","MARUTI","SUNPHARMA","TITAN","ULTRACEMCO",
    "ONGC","POWERGRID","NTPC","ADANIENT","ADANIPORTS","ADANIGREEN",
    "WIPRO","TECHM","JSWSTEEL","TATASTEEL","COALINDIA","GRASIM",
    "HDFCLIFE","BAJAJFINSV","NESTLEIND","DIVISLAB","DRREDDY","CIPLA",
    "EICHERMOT","APOLLOHOSP","BRITANNIA","HEROMOTOCO","HINDALCO",
    "INDUSINDBK","SBILIFE","BPCL","IOC","VEDL","UPL","TATAMOTORS",
    "AMBUJACEM","SHREECEM","ACC","GODREJCP","PIDILITIND","DLF",
    "SIEMENS","ABB","HAL","BEL","BHEL","IRCTC","DMART","ZOMATO",
    "NYKAA","PAYTM","PNB","BANKBARODA","CANBK","IDFCFIRSTB",
    "FEDERALBNK","LICI","ICICIGI","ICICIPRULI","CHOLAFIN","MUTHOOTFIN",
    "MANAPPURAM","SRF","LUPIN","BIOCON","AUROPHARMA","ALKEM",
    "GLENMARK","TORNTPHARM","ASHOKLEY","TVSMOTOR","BAJAJ-AUTO",
    "MOTHERSON","BOSCHLTD","EXIDEIND","HAVELLS","POLYCAB","DABUR",
    "MARICO","COLPAL","TATACONSUM","UBL","UNITDSPR","BERGEPAINT",
    "KANSAINER","PAGEIND","TRENT","ADANIPOWER","TATAPOWER",
    "JSWENERGY","NHPC","RECLTD","PFC","IEX","CAMS","CDSL","MCX","BSE",
    "NAUKRI","INDIAMART","INFOEDGE","MPHASIS","COFORGE","PERSISTENT",
    "LTIM","KPITTECH","SONACOMS","AARTIIND","DEEPAKNTR","ATUL",
    "VINATIORGA","PIIND","COROMANDEL","OBEROIRLTY","PHOENIXLTD",
    "PRESTIGE","BRIGADE","GMRINFRA","ADANITRANS","DELHIVERY","IRFC",
    "HUDCO","NBCC","RVNL","IRB","KEI","CGPOWER","SCHNEIDER",
    "ABBOTINDIA","PFIZER","SANOFI","GLAXO", "TMPV"
]

async def main():
    repo = MongoRepository(get_db())

    success = skipped = failed = 0

    print("\n🚀 BULK INGESTION STARTED")
    print("=" * 60)

    for i, symbol in enumerate(NSE_SYMBOLS, start=1):
        try:
            print(f"[{i}/{len(NSE_SYMBOLS)}] {symbol}", end=" ")

            # if await repo.company_exists(symbol):
            #     skipped += 1
            #     print("⏭️ Already Exists")
            #     continue

            result = await ingest_symbol(symbol)

            # Extract relevant fields for clean company document
            payload = result["payload"]
            company_data = payload.get("company", {})
            metadata = payload.get("metadata", {})
            
            clean_doc = {
                "symbol": result["symbol"],
                "name": company_data.get("name") or metadata.get("company_name") or result["symbol"],
                "sector": company_data.get("sector") or metadata.get("sector") or "Unknown",
                "industry": company_data.get("industry") or "Unknown",
                "profile": {
                    "about": company_data.get("about", ""),
                    "management": result.get("storage_payload", {}).get("fundametrics_response", {}).get("management", [])
                },
                "coverage": result["payload"].get("coverage"),
                "fundametrics_response": result.get("storage_payload", {}).get("fundametrics_response", {}),
                "last_ingested": datetime.now(timezone.utc),
                "last_updated": datetime.now(timezone.utc),
                "data_sources": metadata.get("sources", [])
            }

            await repo.upsert_company(
                symbol=result["symbol"],
                payload=clean_doc
            )

            success += 1
            print("✅ Ingested + Saved")


            await asyncio.sleep(3)  # Rate-limit safe

        except Exception as e:
            failed += 1
            print(f"❌ {str(e)[:120]}")

    print("\n📊 INGESTION SUMMARY")
    print("=" * 60)
    print(f"✅ Success : {success}")
    print(f"⏭️ Skipped : {skipped}")
    print(f"❌ Failed : {failed}")
    print(f"📦 MongoDB Companies : {await repo.count_companies()}")
    print("🎉 DONE")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        NSE_SYMBOLS = sys.argv[1:]
    asyncio.run(main())
