import asyncio
import httpx
import sys
import pandas as pd
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
        print("Fetching data for Excel export...")
        screener_html = await fetch_html(client, screener_url, common_headers)
        trendlyne_main_html = await fetch_html(client, trendlyne_main_url, common_headers)
        trendlyne_about_html = await fetch_html(client, trendlyne_about_url, common_headers | {"X-Requested-With": "XMLHttpRequest"})

    output_file = "MRF_Data_Report.xlsx"
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        
        # 1. Overview Sheet (Profile & Management)
        if trendlyne_main_html and trendlyne_about_html:
            tp_main = TrendlyneParser(trendlyne_main_html, "MRF")
            tp_about = TrendlyneParser(trendlyne_about_html, "MRF")
            
            sector_industry = tp_main.extract_sector_industry()
            profile_data = tp_about.extract_profile_and_mgmt()
            
            overview_data = [
                ["Section", "Details"],
                ["Sector", sector_industry.get('sector', 'N/A')],
                ["Industry", sector_industry.get('industry', 'N/A')],
                ["About", profile_data.get('about', 'N/A')],
                ["", ""]
            ]
            
            overview_data.append(["Management Name", "Designation"])
            for exec in profile_data.get('executives', []):
                overview_data.append([exec.get('name'), exec.get('designation')])
            for director in profile_data.get('management', []):
                overview_data.append([director.get('name'), director.get('designation')])
                
            df_overview = pd.DataFrame(overview_data[1:], columns=overview_data[0])
            df_overview.to_sheet_name = "Overview"
            df_overview.to_excel(writer, sheet_name="Overview", index=False)

        # 2. Fundamentals & Growth
        if screener_html:
            sp = ScreenerParser(screener_html, "MRF")
            
            # Fundamentals
            ratios = sp.get_ratios()
            df_fundamentals = pd.DataFrame(list(ratios.items()), columns=["Metric", "Value"])
            df_fundamentals.to_excel(writer, sheet_name="Fundamentals", index=False)
            
            # Growth
            growth = sp.get_ranges_tables()
            if growth:
                growth_list = []
                for title, data in growth.items():
                    growth_list.append({"Category": title, "Period": "", "Value": ""})
                    for k, v in data.items():
                        growth_list.append({"Category": "", "Period": k, "Value": v})
                    growth_list.append({"Category": "", "Period": "", "Value": ""})
                
                df_growth = pd.DataFrame(growth_list)
                df_growth.to_excel(writer, sheet_name="Growth", index=False)
            
            # Financial Tables
            tables = sp.get_financial_tables()
            for table_name, data in tables.items():
                if data:
                    df_table = pd.DataFrame(data)
                    # Sheet names must be <= 31 chars
                    sheet_name = table_name[:31]
                    df_table.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\nSuccessfully generated {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
