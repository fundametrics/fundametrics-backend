"""
Robust NSE Registry Sync with Batch Processing
Syncs all NSE companies from EQUITY_L.csv to MongoDB
"""
import asyncio
import httpx
import csv
from io import StringIO
from pymongo import MongoClient
from datetime import datetime

# Configuration
MONGO_URI = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BATCH_SIZE = 100

async def main():
    print("=" * 70)
    print("NSE REGISTRY SYNC - ROBUST BATCH PROCESSOR")
    print("=" * 70)
    
    # Step 1: Fetch CSV
    print("\n[1/4] Fetching NSE EQUITY_L.csv...")
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            resp = await client.get(NSE_URL, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            csv_content = resp.text
        print(f"✅ Downloaded {len(csv_content)} bytes")
    except Exception as e:
        print(f"❌ Failed to fetch CSV: {e}")
        return
    
    # Step 2: Parse CSV
    print("\n[2/4] Parsing company data...")
    reader = csv.DictReader(StringIO(csv_content))
    companies = []
    
    for row in reader:
        symbol = row.get('SYMBOL', '').strip().upper()
        name = row.get('NAME OF COMPANY', '').strip()
        
        if symbol:
            companies.append({
                "symbol": symbol,
                "name": name if name else symbol,
                "exchange": "NSE",
                "sector": "General",  # Will be updated during ingestion
                "updated_at": datetime.utcnow().isoformat()
            })
    
    print(f"✅ Parsed {len(companies)} companies")
    
    # Step 3: Connect to MongoDB
    print("\n[3/4] Connecting to MongoDB...")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Test connection
        db = client.get_database("fundametrics")
        col = db["companies_registry"]
        print(f"✅ Connected to database: {db.name}")
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return
    
    # Step 4: Batch Upsert
    print(f"\n[4/4] Upserting in batches of {BATCH_SIZE}...")
    
    inserted = 0
    updated = 0
    errors = 0
    
    for i in range(0, len(companies), BATCH_SIZE):
        batch = companies[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (len(companies) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n  Batch {batch_num}/{total_batches} ({len(batch)} companies)...", end=" ")
        
        try:
            for company in batch:
                result = col.update_one(
                    {"symbol": company["symbol"]},
                    {"$set": {
                        "name": company["name"],
                        "exchange": "NSE",
                        "updated_at": company["updated_at"]
                    }, "$setOnInsert": {
                        "sector": "General",
                        "is_analyzed": False
                    }},
                    upsert=True
                )
                
                if result.upserted_id:
                    inserted += 1
                elif result.modified_count > 0:
                    updated += 1
            
            print(f"✅ Done")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            errors += 1
    
    # Final Count
    total_count = col.count_documents({})
    
    print("\n" + "=" * 70)
    print("SYNC COMPLETE!")
    print("=" * 70)
    print(f"  New Companies Added:     {inserted}")
    print(f"  Existing Updated:        {updated}")
    print(f"  Errors:                  {errors}")
    print(f"  Total in Registry:       {total_count}")
    print("=" * 70)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
