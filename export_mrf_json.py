import asyncio
import httpx
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scraper.sources.screener_parser import ScreenerParser
from scraper.sources.trendlyne_parser import TrendlyneParser

async def fetch_html(client, url, headers):
    try:
        r = await client.get(url, headers=headers)
        if r.status_code == 200:
            return r.text
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def main():
    common_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    screener_url = "https://www.screener.in/company/MRF/consolidated/"
    trendlyne_main_url = "https://trendlyne.com/equity/883/MRF/mrf-ltd/"
    trendlyne_about_url = "https://trendlyne.com/equity/about/883/MRF/mrf-ltd/"
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print("Fetching data for JSON export...")
        screener_html = await fetch_html(client, screener_url, common_headers)
        trendlyne_main_html = await fetch_html(client, trendlyne_main_url, common_headers)
        trendlyne_about_html = await fetch_html(client, trendlyne_about_url, common_headers | {"X-Requested-With": "XMLHttpRequest"})

    results = {
        "symbol": "MRF",
        "company_profile": {},
        "fundamentals": {},
        "growth_metrics": {},
        "financial_tables": {}
    }

    # 1. Trendlyne Data (Profile & Management)
    if trendlyne_main_html and trendlyne_about_html:
        tp_main = TrendlyneParser(trendlyne_main_html, "MRF")
        tp_about = TrendlyneParser(trendlyne_about_html, "MRF")
        
        sector_industry = tp_main.extract_sector_industry()
        profile_data = tp_about.extract_profile_and_mgmt()
        
        results["company_profile"] = {
            "sector": sector_industry.get('sector'),
            "industry": sector_industry.get('industry'),
            "about": profile_data.get('about'),
            "management": profile_data.get('executives', []) + profile_data.get('management', [])
        }

    # 2. Screener Data (Fundamentals & Financials)
    if screener_html:
        sp = ScreenerParser(screener_html, "MRF")
        results["fundamentals"] = sp.get_ratios()
        results["growth_metrics"] = sp.get_ranges_tables()
        results["financial_tables"] = sp.get_financial_tables()

    output_file = "MRF_data_structured.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nSuccessfully generated {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
