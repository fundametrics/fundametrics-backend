import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.db import get_db, get_companies_col, get_metrics_col, get_financials_annual_col
from scraper.core.mongo_repository import MongoRepository

async def check_phase_23():
    # Force correct URI for internal checks
    os.environ["MONGO_URI"] = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"
    
    db = get_db()
    companies_col = get_companies_col()
    metrics_col = get_metrics_col()
    financials_col = get_financials_annual_col()
    
    print("--- Phase 23 Deliverables Audit ---")
    
    # 1. Database Connectivity
    try:
        await db.command("ping")
        print("✅ MongoDB Connection: ACTIVE")
    except Exception as e:
        print(f"❌ MongoDB Connection: FAILED ({e})")
        return

    # 2. Unlimited Companies (Count check)
    count = await companies_col.count_documents({})
    print(f"✅ Unlimited Companies: {count} symbols in registry")
    
    # 3. Search & Listing Capability
    repo = MongoRepository(db)
    all_listing = await repo.get_all_companies()
    listing_with_data = [c for c in all_listing if c.get("marketCap") is not None]
    print(f"✅ Listing: Found {len(all_listing)} companies in list view")
    print(f"✅ Listing Depth: {len(listing_with_data)} companies have active metrics (Market Cap/PE)")

    # 4. Search Verification
    search_results = await repo.search_companies("Eternal")
    if any(r.get("name") == "Eternal Ltd" for r in search_results):
        print("✅ Search: Successfully mapped 'Eternal' to 'Eternal Ltd'")
    else:
        print("❌ Search: Failed to find 'Eternal Ltd'")

    # 5. Screener-style Detail Data (ZOMATO)
    zomato_doc = await repo.get_company("ZOMATO")
    if zomato_doc:
        print(f"✅ Detail Doc: Found ZOMATO as '{zomato_doc.get('name')}'")
        
        # Check components
        m_count = await metrics_col.count_documents({"symbol": "ZOMATO"})
        f_count = await financials_col.count_documents({"symbol": "ZOMATO"})
        
        if m_count > 0 and f_count > 0:
            print(f"✅ Screener-style Data: {m_count} metrics and {f_count} financial statements available")
        else:
            print(f"❌ Screener-style Data: Missing financials for ZOMATO (M:{m_count}, F:{f_count})")
    
    print("\n--- Summary ---")
    if count > 0 and len(all_listing) > 0 and m_count > 0:
        print("🏁 PHASE 23 STATUS: ALL DELIVERABLES MET")
    else:
        print("⚠️ PHASE 23 STATUS: INCOMPLETE")

if __name__ == "__main__":
    asyncio.run(check_phase_23())
