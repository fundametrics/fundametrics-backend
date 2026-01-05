import asyncio
import sys
import os
import pandas as pd
from tabulate import tabulate

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.sources.screener import ScreenerScraper
from scraper.core.fetcher import Fetcher
from scraper.utils.logger import setup_logging

async def show_financials(symbol: str):
    setup_logging()
    
    async with Fetcher() as fetcher:
        screener = ScreenerScraper(fetcher)
        data = await screener.scrape_stock(symbol)
        
        output_lines = []
        output_lines.append(f"FINANCIAL DATA FOR: {symbol}")
        output_lines.append(f"WEBSITE: {data.get('website_url', 'N/A')}")
        output_lines.append("="*80)
        
        tables = data.get('financial_tables', {})
        
        for name, rows in tables.items():
            if not rows:
                continue
            
            df = pd.DataFrame(rows)
            df = df.fillna('')
            
            output_lines.append(f"\n{name.upper()} ({len(rows)} metrics)")
            output_lines.append("-" * 120)
            output_lines.append(tabulate(df, headers='keys', tablefmt='grid', showindex=False))
            output_lines.append("-" * 120)
            
        with open("tcs_financials_utf8.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
            
    print("Financials saved to tcs_financials_utf8.txt")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "TCS"
    asyncio.run(show_financials(symbol))
