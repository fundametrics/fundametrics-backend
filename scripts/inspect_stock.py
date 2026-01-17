
import pymongo
import os
import certifi
import json

MONGO_URI = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"

def inspect_data():
    client = pymongo.MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["fundametrics"]
    col = db["companies"]
    
    targets = ["TATAMOTORS", "ZOMATO", "TMCV", "TMPV"]
    
    for sym in targets:
        print(f"\n{'='*40}")
        print(f"Checking {sym}")
        print(f"{'='*40}")
        
        doc = col.find_one({"symbol": sym})
        if not doc:
            print("❌ No data found in 'companies' collection.")
            # Check registry mapping
            reg = db.companies_registry.find_one({"symbol": sym})
            if reg:
                print("✅ Found in registry.")
            else:
                print("❌ Not in registry either. Maybe invalid symbol?")
                # Try close match
                similar = list(db.companies_registry.find({"symbol": {"$regex": sym, "$options": "i"}}).limit(3))
                if similar:
                     print(f"👉 Maybe: {[s['symbol'] for s in similar]}")
            continue

        resp = doc.get("fundametrics_response", {})
        if not resp:
             print("❌ Data document exists but 'fundametrics_response' is empty.")
             continue
             
        # Check components
        metrics = resp.get("computed_metrics", [])
        financials = resp.get("annual_financials", [])
        
        print(f"Metrics Count: {len(metrics)}")
        if metrics:
            print(f"Sample Metric: {metrics[0]['metric_name']} = {metrics[0]['value']}")
        else:
            print("⚠️ No metrics computed.")
            
        print(f"Financials Years: {len(financials)}")
        if financials:
            latest = financials[-1] # Assuming sorted?
            print(f"Latest Financial Year: {latest.get('year', 'Unknown')}")
        else:
             print("⚠️ No financials found.")
             
        error = doc.get("last_error")
        if error:
            print(f"⚠️ Last recorded error: {error}")

if __name__ == "__main__":
    inspect_data()
