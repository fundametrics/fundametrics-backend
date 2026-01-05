"""
Test Script - Verify Screener Scraper
======================================

Runs a live scrape for RELIANCE and saves structured JSON output.
"""

import asyncio
import json
from pathlib import Path
from scraper.core.fetcher import Fetcher
from scraper.sources.screener import ScreenerScraper
from scraper.utils.logger import setup_logging, get_logger

async def test_screener_scrape():
    # Setup logging
    setup_logging()
    log = get_logger(__name__)
    
    log.info("Starting Screener.in live scrape test")
    
    # Use real-world-like fetcher settings
    try:
        async with Fetcher(max_retries=2) as fetcher:
            scraper = ScreenerScraper(fetcher)
            
            symbol = "RELIANCE"
            data = await scraper.scrape_stock(symbol)
            
            if data:
                # Save to JSON
                output_dir = Path("data/processed")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_file = output_dir / f"{symbol.lower()}_screener.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                log.success(f"Scrape successful! Data saved to {output_file}")
                
                # Print a summary
                print("\n" + "="*50)
                print(f"Screener.in Data for {data.get('company_name')} ({symbol})")
                print("="*50)
                print(f"Market Cap: {data.get('ratios', {}).get('Market Cap')}")
                print(f"Current Price: {data.get('ratios', {}).get('Current Price')}")
                print(f"P/E Ratio: {data.get('ratios', {}).get('Stock P/E')}")
                print(f"Tables Extracted: {list(data.get('financial_tables', {}).keys())}")
                print(f"Shareholding Rows: {len(data.get('shareholding_pattern', []))}")
                print("="*50 + "\n")
            else:
                log.error("Failed to scrape data")
    except Exception as e:
        import traceback
        log.error(f"Test failed with error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_screener_scrape())
