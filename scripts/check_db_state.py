
import pymongo
import os
import certifi

MONGO_URI = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"

def check_state():
    print("Connecting to MongoDB...")
    try:
        client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client["fundametrics"]
        
        # 1. Check Registry Count
        reg_count = db.companies_registry.count_documents({})
        print(f"\n[REGISTRY] Count: {reg_count}")
        
        # 2. Check Analyzed Count
        analyzed_count = db.companies.count_documents({})
        print(f"[ANALYZED] Companies: {analyzed_count}")
        
        # 3. Check Specific Companies
        targets = ["TATAMOTORS", "TMCV", "TMPV", "ZOMATO"]
        print("\n[CHECKING] Specific Companies:")
        for sym in targets:
            # Check registry
            reg_doc = db.companies_registry.find_one({"symbol": sym})
            in_reg = "YES" if reg_doc else "NO"
            
            # Check analyzed data
            data_doc = db.companies.find_one({"symbol": sym})
            in_data = "YES" if data_doc else "NO"
            
            details = ""
            if data_doc:
                # Check if 'fundametrics_response' is populated
                has_resp = "YES" if data_doc.get("fundametrics_response") else "NO"
                details = f"(Has Response: {has_resp})"
            
            print(f"  {sym:<12} Registry: {in_reg} | Data: {in_data} {details}")

            if not reg_doc and not data_doc:
                similar = list(db.companies_registry.find({"symbol": {"$regex": sym, "$options": "i"}}).limit(3))
                if similar:
                    print(f"    -> Did you mean: {[s['symbol'] for s in similar]}?")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_state()
