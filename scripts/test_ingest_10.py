"""
Test Bulk Ingestion - 10 Companies

Quick test before full 200+ company ingestion
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.mongo_repository import MongoRepository
from scraper.core.ingestion import ingest_symbol
from scraper.core.repository import DataRepository

# Test with 10 major companies
TEST_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
    "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "LT"
]

async def migrate_company(symbol: str, mongo_repo: MongoRepository, sqlite_repo: DataRepository) -> bool:
    """Migrate one company from SQLite to MongoDB"""
    try:
        data = sqlite_repo.get_latest(symbol)
        if not data:
            return False
        
        fundametrics_response = data.get("fundametrics_response", {})
        company_data = fundametrics_response.get("company", {})
        
        # Save company
        await mongo_repo.upsert_company(symbol, {
            "name": company_data.get("name", f"{symbol} Limited"),
            "sector": company_data.get("sector", "Not disclosed"),
            "industry": company_data.get("industry", "—"),
            "about": company_data.get("about", "")
        })
        
        # Save financials
        yearly_financials = data.get("yearly_financials", {})
        for year, data_dict in yearly_financials.items():
            await mongo_repo.upsert_financials_annual(
                symbol=symbol, year=year, statement_type="income_statement",
                data=data_dict,
                metadata={"source": "screener.in", "scraped_at": datetime.now(timezone.utc)}
            )
        
        # Save metrics
        for metric in fundametrics_response.get("fundametrics_metrics", []):
            if metric.get("value") is not None:
                await mongo_repo.upsert_metric(
                    symbol=symbol, period="Latest",
                    metric_name=metric.get("metric_name"),
                    value=metric.get("value"),
                    unit=metric.get("unit", ""),
                    confidence=metric.get("confidence", 0),
                    trust_score=metric.get("trust_score"),
                    drift=metric.get("drift")
                )
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

async def main():
    print("Test Ingestion: 10 Companies")
    print("=" * 50)
    
    mongo_repo = MongoRepository()
    sqlite_repo = DataRepository()
    
    success = 0
    for i, symbol in enumerate(TEST_SYMBOLS, 1):
        print(f"[{i}/10] {symbol}...", end=" ")
        
        try:
            # Try scraping
            try:
                await ingest_symbol(symbol)
            except:
                pass
            
            # Migrate to MongoDB
            if await migrate_company(symbol, mongo_repo, sqlite_repo):
                success += 1
                print("✅")
            else:
                print("⏭️")
            
            await asyncio.sleep(2)  # Short delay
        except Exception as e:
            print(f"❌ {e}")
    
    print()
    print(f"Success: {success}/10")
    
    stats = await mongo_repo.get_stats()
    print(f"MongoDB: {stats['companies']} companies")

if __name__ == "__main__":
    asyncio.run(main())
