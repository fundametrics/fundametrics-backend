"""
Ingest RELIANCE into MongoDB - Phase 22 Proof of Concept

This script:
1. Scrapes RELIANCE data using existing scraper
2. Reads from SQLite (temporary bridge)
3. Saves to MongoDB using MongoRepository
4. Verifies data in Atlas
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment
load_dotenv()
load_dotenv('.env.production')

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.mongo_repository import MongoRepository
from scraper.core.ingestion import ingest_symbol
from scraper.core.repository import DataRepository

async def main():
    print("=" * 60)
    print("Phase 22: Ingesting RELIANCE into MongoDB")
    print("=" * 60)
    print()
    
    symbol = "RELIANCE"
    
    # Step 1: Use existing scraper to get data
    print(f"Step 1: Scraping {symbol} data...")
    try:
        result = await ingest_symbol(symbol)
        print(f"SUCCESS: Scraped successfully")
        print(f"   Blocks ingested: {result['blocks_ingested']}")
    except Exception as e:
        print(f"ERROR: Scraping failed: {e}")
        print("Trying to use existing SQLite data...")
    
    # Step 2: Get data from SQLite
    print()
    print(f"Step 2: Reading data from SQLite...")
    sqlite_repo = DataRepository()
    data = sqlite_repo.get_latest(symbol)
    if not data:
        print(f"ERROR: No data found in SQLite for {symbol}")
        print("Please run: py -m scraper.core.ingestion RELIANCE")
        return
    print(f"SUCCESS: Data loaded from SQLite")
    
    # Step 3: Transform and save to MongoDB
    print()
    print(f"Step 3: Saving to MongoDB...")
    mongo_repo = MongoRepository()
    
    fundametrics_response = data.get("fundametrics_response", {})
    
    # 3a. Save company profile
    company_data = fundametrics_response.get("company", {})
    await mongo_repo.upsert_company(symbol, {
        "name": company_data.get("name"),
        "sector": company_data.get("sector"),
        "industry": company_data.get("industry"),
        "about": company_data.get("about", "")
    })
    print(f"  - Company profile saved")
    
    # 3b. Save financials (from yearly_financials)
    yearly_financials = data.get("yearly_financials", {})
    financials_count = 0
    for year, data_dict in yearly_financials.items():
        # Save as income_statement (simplified for now)
        await mongo_repo.upsert_financials_annual(
            symbol=symbol,
            year=year,
            statement_type="income_statement",
            data=data_dict,
            metadata={
                "source": "screener.in",
                "scraped_at": datetime.now(timezone.utc),
                "migrated_from": "sqlite"
            }
        )
        financials_count += 1
    print(f"  - Financials saved ({financials_count} years)")
    
    # 3c. Save metrics (from fundametrics_metrics)
    fundametrics_metrics = fundametrics_response.get("fundametrics_metrics", [])
    metrics_count = 0
    for metric in fundametrics_metrics:
        if metric.get("value") is not None:  # Only save metrics with values
            await mongo_repo.upsert_metric(
                symbol=symbol,
                period="Latest",
                metric_name=metric.get("metric_name"),
                value=metric.get("value"),
                unit=metric.get("unit", ""),
                confidence=metric.get("confidence", 0),
                trust_score=metric.get("trust_score"),
                drift=metric.get("drift"),
                explainability=metric.get("explainability"),
                source_provenance=metric.get("source_provenance")
            )
            metrics_count += 1
    print(f"  - Metrics saved ({metrics_count} metrics)")
    
    # 3d. Save ownership
    shareholding = fundametrics_response.get("shareholding", {})
    if shareholding and shareholding.get("status") == "available":
        await mongo_repo.upsert_ownership(
            symbol=symbol,
            quarter="Latest",
            summary=shareholding.get("summary", {}),
            insights=shareholding.get("insights", [])
        )
        print(f"  - Ownership saved")
    else:
        print(f"  - Ownership: Not available")
    
    # 3e. Save trust metadata
    metadata = fundametrics_response.get("metadata", {})
    await mongo_repo.upsert_trust_metadata(
        symbol=symbol,
        run_id=metadata.get("run_id", "mongo-migration-001"),
        coverage=fundametrics_response.get("coverage", {}),
        warnings=metadata.get("warnings", []),
        data_sources=metadata.get("data_sources", {})
    )
    print(f"  - Trust metadata saved")
    
    # Step 4: Verify in MongoDB
    print()
    print(f"Step 4: Verifying data in MongoDB...")
    stats = await mongo_repo.get_stats()
    print(f"  - Companies: {stats['companies']}")
    print(f"  - Financials: {stats['financials_annual']}")
    print(f"  - Metrics: {stats['metrics']}")
    print(f"  - Ownership: {stats['ownership']}")
    
    print()
    print("=" * 60)
    print(f"SUCCESS: {symbol} ingested into MongoDB!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart API server:")
    print("   py -m uvicorn scraper.api.app:app --port 8001 --reload")
    print()
    print("2. Test API:")
    print("   curl http://localhost:8001/stocks/RELIANCE")
    print()
    print("3. Open frontend:")
    print("   http://localhost:5173/stocks/RELIANCE")
    print()
    print("4. Verify in MongoDB Atlas:")
    print("   https://cloud.mongodb.com/")

if __name__ == "__main__":
    asyncio.run(main())
