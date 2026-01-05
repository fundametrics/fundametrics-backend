import asyncio
import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scraper.sources.moneycontrol import MoneycontrolScraper
from scraper.utils.logger import logger

async def test_live_mc_scrape():
    scraper = MoneycontrolScraper()
    
    # Test with RELIANCE
    symbol = "RELIANCE"
    data = await scraper.scrape_stock(symbol)
    
    if data:
        print(f"\nScraped Data for {symbol}:")
        print(json.dumps(data, indent=2))
        
        # Save to file
        output_dir = "data/processed"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{symbol.lower()}_moneycontrol.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nData saved to {output_path}")
        logger.success("Scrape successful!")
    else:
        logger.error(f"Scrape failed for {symbol}")

if __name__ == "__main__":
    asyncio.run(test_live_mc_scrape())
