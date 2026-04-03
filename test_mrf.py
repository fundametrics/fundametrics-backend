import asyncio
import logging
import sys
import os

# Add the current directory to sys.path to allow importing from scraper
sys.path.append(os.getcwd())

from scraper.core.market_facts_engine import MarketFactsEngine

async def test_mrf():
    logging.basicConfig(level=logging.INFO)
    engine = MarketFactsEngine()
    symbols = ["INFY.NS", "MRF.NS", "ICICIBANK.NS", "BHEL.NS", "TATASTEEL.NS"]
    
    print("\n" + "="*50)
    print("SYMBOL-AWARE DATA EXTRACTION TEST (ASCII SAFE)")
    print("="*50)
    
    for sym in symbols:
        print(f"\n[TESTING] {sym}")
        try:
            data = await engine._scrape_index_html(sym)
            if data:
                print(f"SUCCESS for {sym}:")
                print(f"  Price: {data.get('current_price')}")
                print(f"  Change: {data.get('change_percent', 0):.2f}%")
                print(f"  Currency: {data.get('currency')}")
            else:
                print(f"FAILED: No data extracted for {sym}")
        except Exception as e:
            print(f"ERROR for {sym}: {e}")

if __name__ == "__main__":
    asyncio.run(test_mrf())
