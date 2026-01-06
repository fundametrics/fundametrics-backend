"""
Database Indexing Script for MongoDB Atlas
Prevents duplicates and speeds up queries.
"""
import asyncio
import os
from scraper.core.db import get_db

async def create_indexes():
    db = get_db()
    
    # 1. Companies collection
    companies_col = db["companies"]
    print("Creating index on companies.symbol (unique)...")
    await companies_col.create_index("symbol", unique=True)
    
    # 2. Trust Reports collection
    trust_reports_col = db["trust_reports"]
    print("Creating index on trust_reports.symbol...")
    await trust_reports_col.create_index("symbol")
    
    # 3. Registry collection
    registry_col = db["companies_registry"]
    print("Creating index on companies_registry.symbol (unique)...")
    await registry_col.create_index("symbol", unique=True)
    
    print("✅ All indexes created successfully!")

if __name__ == "__main__":
    asyncio.run(create_indexes())
