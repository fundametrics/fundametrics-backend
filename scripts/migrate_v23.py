import asyncio
from scraper.core.db import get_db, get_companies_col

async def migrate():
    print("🚀 Starting migration to Phase 23 Schema...")
    col = get_companies_col()
    cursor = col.find({})
    
    count = 0
    async for doc in cursor:
        updates = {}
        fundametrics = doc.get("fundametrics_response", {})
        
        # 1. Name
        if "name" not in doc:
            name = fundametrics.get("company", {}).get("name") or fundametrics.get("metadata", {}).get("company_name") or doc.get("symbol")
            if name: updates["name"] = name

        # 2. Sector/Industry
        if "sector" not in doc:
            sec = fundametrics.get("company", {}).get("sector") or fundametrics.get("metadata", {}).get("sector")
            if sec: updates["sector"] = sec
            
        if "industry" not in doc:
             ind = fundametrics.get("company", {}).get("industry")
             if ind: updates["industry"] = ind
             
        # 3. Profile
        if "profile" not in doc:
            profile = {
                "about": fundametrics.get("company", {}).get("about", ""),
                "management": fundametrics.get("management", []) if fundametrics.get("management") else []
            }
            updates["profile"] = profile
            
        # 4. Coverage (from fundametrics_response)
        if "coverage" not in doc:
            cov = fundametrics.get("coverage")
            if cov: updates["coverage"] = cov
            
        if updates:
            # Update the doc
            await col.update_one({"_id": doc["_id"]}, {"$set": updates})
            count += 1
            if count % 10 == 0:
                print(f"Migrated {count} companies...")
            
    print(f"✅ Migration complete. Updated {count} documents.")

if __name__ == "__main__":
    asyncio.run(migrate())
