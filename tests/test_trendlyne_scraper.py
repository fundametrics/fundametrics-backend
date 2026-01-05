import asyncio
import json
import logging
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.fetcher import Fetcher
from scraper.sources.trendlyne import TrendlyneScraper

async def test_trendlyne():
    logging.basicConfig(level=logging.INFO)
    
    fetcher = Fetcher()
    scraper = TrendlyneScraper(fetcher)
    
    symbols = ["RELIANCE", "TCS"]
    for symbol in symbols:
        data = await scraper.scrape_stock(symbol)
        
        print(f"\n--- Trendlyne Data for {symbol} ---")
        if data:
            print(f"Sector: {data.get('sector')}")
            print(f"Industry: {data.get('industry')}")
            about_text = data.get('about') or ""
            print(f"About Snippet: {about_text[:200]}...")
            print(f"Management Count: {len(data.get('management', []))}")
            print(f"Executives Count: {len(data.get('executives', []))}")
            
            # Save to file for inspection
            with open(f"trendlyne_{symbol}.json", "w") as f:
                json.dump(data, f, indent=2)
            print(f"Full data saved to trendlyne_{symbol}.json")
        else:
            print(f"Failed to scrape data for {symbol}.")

if __name__ == "__main__":
    asyncio.run(test_trendlyne())
