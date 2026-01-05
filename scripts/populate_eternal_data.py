import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db, get_financials_annual_col, get_ownership_col

async def main():
    # Force correct URI
    os.environ["MONGO_URI"] = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"
    
    repo = MongoRepository(get_db())
    symbol = "ZOMATO"
    
    print(f"Injecting detailed financial data for {symbol}...")
    
    # 1. Annual Financials (P&L, BS, CF, Ratios)
    financials_col = get_financials_annual_col()
    
    p_and_l_data = [
        {"year": 2022, "Sales": 4192, "Expenses": 5043, "Operating Profit": -851, "Net Profit": -1222, "EPS": -1.53},
        {"year": 2023, "Sales": 7079, "Expenses": 8290, "Operating Profit": -1211, "Net Profit": -971, "EPS": -1.13},
        {"year": 2024, "Sales": 12114, "Expenses": 12053, "Operating Profit": 61, "Net Profit": 351, "EPS": 0.41}
    ]
    
    balance_sheet_data = [
        {"year": 2022, "Share Capital": 764, "Reserves": 15832, "Borrowings": 55, "Total Assets": 17354},
        {"year": 2023, "Share Capital": 855, "Reserves": 18231, "Borrowings": 48, "Total Assets": 20124},
        {"year": 2024, "Share Capital": 883, "Reserves": 22210, "Borrowings": 52, "Total Assets": 23650}
    ]
    
    cash_flow_data = [
        {"year": 2022, "Cash from Operating Activity": -701, "Cash from Investing Activity": -1202, "Cash from Financing Activity": 1850, "Net Cash Flow": -53},
        {"year": 2023, "Cash from Operating Activity": -123, "Cash from Investing Activity": -2105, "Cash from Financing Activity": 2300, "Net Cash Flow": 72},
        {"year": 2024, "Cash from Operating Activity": 450, "Cash from Investing Activity": -1500, "Cash from Financing Activity": 1200, "Net Cash Flow": 150}
    ]

    ratios_data = [
        {"year": 2022, "ROE": -11.5, "ROCE": -8.2, "Net Profit Margin": -29.1},
        {"year": 2023, "ROE": -5.3, "ROCE": -6.5, "Net Profit Margin": -13.7},
        {"year": 2024, "ROE": 4.5, "ROCE": 6.8, "Net Profit Margin": 2.9}
    ]

    for data_list, stype in [
        (p_and_l_data, "income_statement"), 
        (balance_sheet_data, "balance_sheet"), 
        (cash_flow_data, "cash_flow"),
        (ratios_data, "ratios_table")
    ]:
        for entry in data_list:
            year = entry.pop("year")
            doc = {
                "symbol": symbol,
                "year": year,
                "statement_type": stype,
                "data": entry,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            await financials_col.update_one(
                {"symbol": symbol, "year": year, "statement_type": stype},
                {"$set": doc},
                upsert=True
            )
    
    print("✅ Financial Tables Injected")

    # 2. Ownership Pattern with History
    ownership_col = get_ownership_col()
    
    # Create a history list for the chart
    history = [
        {"period": "Jun 2024", "promoter": 0.0, "fii": 52.1, "dii": 15.4, "public": 32.5},
        {"period": "Sep 2024", "promoter": 0.0, "fii": 53.5, "dii": 17.1, "public": 29.4},
        {"period": "Dec 2024", "promoter": 0.0, "fii": 54.12, "dii": 18.23, "public": 27.65}
    ]

    ownership_data = {
        "symbol": symbol,
        "quarter": "Dec 2024",
        "promoters": 0.00,
        "fii": 54.12,
        "dii": 18.23,
        "public": 27.65,
        "others": 0.00,
        "history": history,
        "insights": [
             {"title": "Professional Management", "description": "Company has no promoters. Ownership is diversified among institutions."},
             {"title": "Institutional Dominance", "description": "FIIs and DIIs together hold over 72% of the company."},
             {"title": "Increasing DII Stake", "description": "Domestic Mutual Funds have steadily increased stake over the last 3 quarters."}
        ],
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    await ownership_col.update_one(
        {"symbol": symbol},
        {"$set": ownership_data},
        upsert=True
    )
    print("✅ Ownership Pattern Injected")

    # 3. Comprehensive AI Summary
    await repo.upsert_company(symbol, {
        "symbol": symbol,
        "name": "Eternal Ltd",
        "sector": "Services",
        "industry": "Consumer Services",
        "about": "Zomato Limited (rebranded as Eternal Ltd) is an Indian multinational restaurant aggregator and food delivery company. It provides information, menus and user-reviews of restaurants as well as food delivery options from partner restaurants in select cities. The company has recently expanded significantly into quick commerce via its acquisition of Blinkit.",
        "fundametrics_response": {
            "ai_summary": {
                "paragraphs": [
                    "Eternal Ltd (formerly Zomato) has successfully transitioned from a high-burn growth phase to a profitable operation as of FY24. The core food delivery business continues to generate significant cash flow.",
                    "The strategic acquisition and turnaround of Blinkit has positioned Eternal as a leader in India's rapidly expanding quick commerce market, providing a secondary growth engine.",
                    "With a robust institutional ownership of over 70% and a zero-debt balance sheet, the company maintains a very strong financial profile despite the high-competition landscape of online retail."
                ]
            }
        },
        "last_updated": datetime.now(timezone.utc).isoformat()
    })
    print("✅ Company Metadata & AI Summary Updated")

if __name__ == "__main__":
    asyncio.run(main())
