import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db
from dotenv import load_dotenv

async def main():
    # load_dotenv() - failing
    os.environ["MONGO_URI"] = "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority"
    
    repo = MongoRepository(get_db())
    print("Fetching ZOMATO doc...")
    doc = await repo.get_company("ZOMATO")
    if not doc:
        print("Doc not found!")
        return

    fr = doc.get("fundametrics_response", {})
    metrics = fr.get("fundametrics_metrics")
    print(f"Metrics in FR: {metrics}")
    
    if isinstance(metrics, list):
         print(f"Count: {len(metrics)}")
         if len(metrics) > 0:
             print(f"Sample: {metrics[0]}")

if __name__ == "__main__":
    asyncio.run(main())
