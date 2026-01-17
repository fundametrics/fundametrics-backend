"""
Standalone diagnostic - no scraper imports
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority")

async def check_status():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_database("fundametrics")
    
    print("=" * 60)
    print("FUNDAMETRICS DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Check registry count
    registry_col = db["companies_registry"]
    registry_count = await registry_col.count_documents({})
    print(f"\n📊 Companies Registry Count: {registry_count}")
    
    # Check analyzed companies count
    companies_col = db["companies"]
    analyzed_count = await companies_col.count_documents({})
    print(f"📊 Analyzed Companies Count: {analyzed_count}")
    
    # Check how many are pending
    pending = registry_count - analyzed_count
    print(f"⏳ Pending Analysis: {pending}")
    print(f"📈 Progress: {(analyzed_count/registry_count*100):.1f}%")
    
    # Check recent ingestions (last 24 hours)
    from datetime import datetime, timedelta
    yesterday = datetime.utcnow() - timedelta(days=1)
    
    # Try to count recent ones (might not have ingested_at field)
    recent_docs = await companies_col.find({}).sort("_id", -1).limit(100).to_list(length=100)
    print(f"\n📈 Total companies in DB: {analyzed_count}")
    print(f"📈 Last 100 companies fetched for inspection")
    
    # Sample some problematic stocks
    print("\n" + "=" * 60)
    print("CHECKING PROBLEM STOCKS")
    print("=" * 60)
    problem_stocks = ["TATAMOTORS", "TMCV", "TMPV", "ZOMATO"]
    for symbol in problem_stocks:
        doc = await companies_col.find_one({"symbol": symbol})
        if doc:
            has_data = bool(doc.get("fundametrics_response"))
            print(f"✅ {symbol}: Exists | Has Data: {has_data}")
        else:
            # Check if it's in registry
            in_registry = await registry_col.find_one({"symbol": symbol})
            if in_registry:
                print(f"⚠️  {symbol}: In registry but NOT analyzed yet")
            else:
                print(f"❌ {symbol}: NOT in registry")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(check_status())
