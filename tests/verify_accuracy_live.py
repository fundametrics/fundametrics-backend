import asyncio
import sys
import os
import json
from decimal import Decimal

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.sources.screener import ScreenerScraper
from scraper.sources.trendlyne import TrendlyneScraper
from scraper.core.fetcher import Fetcher
from scraper.utils.pipeline import DataPipeline
from scraper.utils.logger import setup_logging

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

async def verify_accuracy(symbol: str):
    setup_logging()
    
    print(f"\n{'='*60}")
    print(f"LIVE ACCURACY AUDIT: {symbol}")
    print(f"{'='*60}")
    
    async with Fetcher() as fetcher:
        screener = ScreenerScraper(fetcher)
        trendlyne = TrendlyneScraper(fetcher)
        pipeline = DataPipeline()
        
        print(f"\n[1/3] Fetching from Screener.in...")
        try:
            screener_data = await screener.scrape_stock(symbol)
            print("  [SUCCESS] Screener Data Fetched")
        except Exception as e:
            print(f"  [FAILED] Screener Fetch: {e}")
            return

        print(f"\n[2/3] Fetching from Trendlyne.com...")
        try:
            trendlyne_data = await trendlyne.scrape_stock(symbol)
            print("  [SUCCESS] Trendlyne Data Fetched")
        except Exception as e:
            print(f"  [FAILED] Trendlyne Fetch: {e}")
            trendlyne_data = {}

        print(f"\n[3/3] Consolidating and Validating...")
        raw_data = {
            "symbol": symbol,
            "company_name": screener_data.get("company_name"),
            "website_url": screener_data.get("website_url"),
            "ratios": screener_data.get("ratios"),
            "financial_tables": screener_data.get("financial_tables"),
            "sector": trendlyne_data.get("sector"),
            "industry": trendlyne_data.get("industry"),
            "about": trendlyne_data.get("about"),
            "management": trendlyne_data.get("management", []),
            "executives": trendlyne_data.get("executives", [])
        }
        
        processed = pipeline.process_stock_data(raw_data)
        cleaned = processed["cleaned_data"]
        report = processed["validation_report"]
        
        print("\n" + "-"*40)
        print("AUDIT RESULTS (CLEANED DATA)")
        print("-"*40)
        
        print(f"Company: {cleaned.get('company_name')}")
        print(f"Website: {cleaned.get('website_url')}")
        print(f"Sector:  {cleaned.get('sector')}")
        print(f"Industry: {cleaned.get('industry')}")

        print("\nFinancial Tables Available:")
        ft = cleaned.get("financial_tables", {})
        for table_name in ft.keys():
            rows = ft[table_name]
            print(f"  - {table_name}: {len(rows)} metrics found")
            if table_name == 'Profit & Loss' and len(rows) > 0:
                print(f"    * Sample: {rows[0].get('Metric')} -> {list(rows[0].keys())[1:]}")
        
        print("\nKey Ratios:")
        ratios = cleaned.get("ratios", {})
        for key, val in ratios.items():
            print(f"  - {key}: {val}")
            
        print("\nManagement (Sample):")
        for member in cleaned.get("management", [])[:3]:
            print(f"  - {member.get('name')} ({member.get('designation')})")

        print("\nValidation Status:")
        if report["is_valid"]:
            print("  PASSED: DATA IS VALID")
        else:
            print("  WARNING: DATA HAS ISSUES:")
            for err in report["errors"]:
                print(f"    - {err}")
        
        print(f"\n{'='*60}")
        print("Audit Complete.")
        print(f"{'='*60}")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
    asyncio.run(verify_accuracy(symbol))
