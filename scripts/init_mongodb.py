"""
MongoDB Initialization Script

Run this script once to:
1. Test MongoDB connection
2. Create indexes
3. Verify database setup
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.db import ping_db, init_indexes, get_db
from scraper.core.mongo_repository import MongoRepository

async def main():
    """Initialize MongoDB"""
    print("Fundametrics MongoDB Initialization")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    load_dotenv('.env.production')
    
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("ERROR: MONGO_URI not found in environment variables")
        print("Please set MONGO_URI in .env or .env.production")
        return
    
    # Mask password in output
    masked_uri = mongo_uri.split('@')[1] if '@' in mongo_uri else mongo_uri
    print(f"Connecting to: ...@{masked_uri}")
    print()
    
    # Test connection
    print("Step 1: Testing MongoDB connection...")
    connected = await ping_db()
    if not connected:
        print("ERROR: Failed to connect to MongoDB")
        print("Please check your MONGO_URI and network connection")
        return
    print("SUCCESS: MongoDB connection successful")
    print()
    
    # Create indexes
    print("Step 2: Creating database indexes...")
    try:
        await init_indexes()
        print("SUCCESS: All indexes created successfully")
    except Exception as e:
        print(f"ERROR: Failed to create indexes: {e}")
        return
    print()
    
    # Verify collections
    print("Step 3: Verifying collections...")
    db = get_db()
    collections = await db.list_collection_names()
    print(f"Collections: {', '.join(collections) if collections else 'None (empty database)'}")
    print()
    
    # Get stats
    print("Step 4: Database statistics...")
    repo = MongoRepository()
    stats = await repo.get_stats()
    print(f"Companies: {stats['companies']}")
    print(f"Annual Financials: {stats['financials_annual']}")
    print(f"Metrics: {stats['metrics']}")
    print(f"Ownership Records: {stats['ownership']}")
    print()
    
    print("=" * 50)
    print("MongoDB initialization complete!")
    print()
    print("Next steps:")
    print("1. Run bulk ingestion: py scripts/bulk_ingest.py")
    print("2. Start API server: py -m uvicorn scraper.api.app:app --reload")
    print("3. Test API: http://localhost:8000/stocks")

if __name__ == "__main__":
    asyncio.run(main())
