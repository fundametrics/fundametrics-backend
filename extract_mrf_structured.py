import asyncio
import httpx
import sys
import os
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
        else:
            print(f"Failed to fetch {url}: {r.status_code}")
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
        print("Fetching data from sources...")
        screener_html = await fetch_html(client, screener_url, common_headers)
        trendlyne_main_html = await fetch_html(client, trendlyne_main_url, common_headers)
        trendlyne_about_html = await fetch_html(client, trendlyne_about_url, common_headers | {"X-Requested-With": "XMLHttpRequest"})

    report_lines = []
    report_lines.append("DATA REPORT FOR: MRF")
    report_lines.append("=" * 80)
    report_lines.append("")

    # --- Trendlyne Data (Profile & Management) ---
    if trendlyne_main_html and trendlyne_about_html:
        report_lines.append("[COMPANY PROFILE]")
        tp_main = TrendlyneParser(trendlyne_main_html, "MRF")
        tp_about = TrendlyneParser(trendlyne_about_html, "MRF")
        
        sector_industry = tp_main.extract_sector_industry()
        profile_data = tp_about.extract_profile_and_mgmt()
        
        report_lines.append(f"Sector: {sector_industry.get('sector', 'N/A')}")
        report_lines.append(f"Industry: {sector_industry.get('industry', 'N/A')}")
        report_lines.append(f"About: {profile_data.get('about', 'N/A')}\n")
        
        report_lines.append("[MANAGEMENT]")
        for exec in profile_data.get('executives', []):
            report_lines.append(f"{exec.get('name')} - {exec.get('designation')}")
        for director in profile_data.get('management', []):
            report_lines.append(f"{director.get('name')} - {director.get('designation')}")
        report_lines.append("")

    # --- Screener Data (Fundamentals & Financials) ---
    if screener_html:
        sp = ScreenerParser(screener_html, "MRF")
        
        report_lines.append("[FUNDAMENTALS]")
        ratios = sp.get_ratios()
        for key, val in ratios.items():
            report_lines.append(f"{key}: {val}")
        report_lines.append("")

        growth = sp.get_ranges_tables()
        if growth:
            report_lines.append("[GROWTH & PERFORMANCE]")
            for title, data in growth.items():
                report_lines.append(f">> {title}")
                for k, v in data.items():
                    report_lines.append(f"{k}: {v}")
                report_lines.append("")
        
        report_lines.append("[FINANCIAL TABLES]")
        tables = sp.get_financial_tables()
        for table_name, data in tables.items():
            report_lines.append(f"\n>> {table_name}")
            if not data:
                report_lines.append("No data found")
                continue
                
            # Header
            headers = list(data[0].keys())
            header_str = " | ".join(headers)
            report_lines.append(header_str)
            report_lines.append("-" * len(header_str))
            
            # Rows
            for row in data:
                row_str = " | ".join([str(row.get(h, "")) for h in headers])
                report_lines.append(row_str)
        report_lines.append("")

    final_report = "\n".join(report_lines)
    
    with open("MRF_consolidated_report.txt", "w", encoding="utf-8") as f:
        f.write(final_report)
    
    print("\n" + "="*40)
    print("CONSOLIDATED REPORT GENERATED: MRF_consolidated_report.txt")
    print("="*40 + "\n")
    print(final_report[:2000] + "\n...")

if __name__ == "__main__":
    asyncio.run(main())
