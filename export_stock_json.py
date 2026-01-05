import asyncio
import httpx
import sys
import json
import argparse
import re
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
        print(f"Failed to fetch {url}: {r.status_code}")
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

async def get_urls(symbol):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://trendlyne.com/"
    }
    
    search_url = f"https://trendlyne.com/member/api/ac_snames/stock/?term={symbol}"
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            r = await client.get(search_url, headers=h)
            if r.status_code == 200 and r.text.strip() != "fail":
                data = r.json()
                if data and isinstance(data, list) and len(data) > 0:
                    exturl = data[0].get('exturl')
                    if exturl:
                        if exturl.startswith('/'):
                            exturl = "https://trendlyne.com" + exturl
                        about_url = exturl.replace("/equity/", "/equity/about/")
                        return exturl, about_url
            
            print(f"Trendlyne API returned status {r.status_code}. Body: {r.text[:500]}")
            # Hardcoded fallbacks for common stocks if search fails
            fallbacks = {
                "ONGC": "https://trendlyne.com/equity/1126/ONGC/oil-natural-gas-corporation-ltd/",
                "MRF": "https://trendlyne.com/equity/883/MRF/mrf-ltd/",
                "COALINDIA": "https://trendlyne.com/equity/353/COALINDIA/coal-india-ltd/",
                "BHEL": "https://trendlyne.com/equity/189/BHEL/bharat-heavy-electricals-ltd/"
            }
            if symbol in fallbacks:
                exturl = fallbacks[symbol]
                about_url = exturl.replace("/equity/", "/equity/about/")
                return exturl, about_url

        except Exception as e:
            print(f"Trendlyne Search Error: {e}")
    return None, None

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol", help="Stock symbol (e.g. ONGC, MRF)")
    args = parser.parse_args()
    symbol = args.symbol.upper()

    print(f"--- SCRAPING DATA FOR: {symbol} ---")
    
    tl_main, tl_about = await get_urls(symbol)
    if not tl_main:
        print(f"Could not find Trendlyne URLs for {symbol}")
        return

    screener_url = f"https://www.screener.in/company/{symbol}/consolidated/"
    
    common_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print(f"Fetching: {screener_url}")
        screener_html = await fetch_html(client, screener_url, common_headers)
        
        print(f"Fetching: {tl_main}")
        trendlyne_main_html = await fetch_html(client, tl_main, common_headers)
        
        print(f"Fetching: {tl_about}")
        trendlyne_about_html = await fetch_html(client, tl_about, common_headers | {"X-Requested-With": "XMLHttpRequest"})

    results = {
        "symbol": symbol,
        "company_profile": {},
        "fundamentals": {},
        "growth_metrics": {},
        "financial_tables": {}
    }

    # 1. Trendlyne Data
    if trendlyne_main_html and trendlyne_about_html:
        tp_main = TrendlyneParser(trendlyne_main_html, symbol)
        tp_about = TrendlyneParser(trendlyne_about_html, symbol)
        
        sector_industry = tp_main.extract_sector_industry()
        profile_data = tp_about.extract_profile_and_mgmt()
        
        results["company_profile"] = {
            "sector": sector_industry.get('sector'),
            "industry": sector_industry.get('industry'),
            "about": profile_data.get('about'),
            "management": profile_data.get('executives', []) + profile_data.get('management', [])
        }

    # 2. Screener Data
    if screener_html:
        sp = ScreenerParser(screener_html, symbol)
        results["fundamentals"] = sp.get_ratios()
        results["financial_tables"] = sp.get_financial_tables()

    output_file = f"{symbol}_data_structured.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nSUCCESS: Generated {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
