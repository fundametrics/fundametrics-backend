"""
MongoDB Database Connection and Collections

This module provides async MongoDB client and collection references
for the Fundametrics application.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, TEXT, DESCENDING
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# MongoDB connection
_client: Optional[AsyncIOMotorClient] = None
_db = None

def get_mongo_uri() -> str:
    """Get MongoDB URI from environment"""
    # Check multiple common env var names for compatibility
    uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or os.getenv("MONGODB_URL")
    if not uri:
        logger.error("MongoDB environment variable (MONGO_URI, MONGODB_URI, or MONGODB_URL) not set!")
        raise ValueError("MongoDB connection string is required in environment variables")
    return uri

def get_client() -> AsyncIOMotorClient:
    """Get MongoDB client (singleton)"""
    global _client
    if _client is None:
        uri = get_mongo_uri()
        _client = AsyncIOMotorClient(uri)
        logger.info("MongoDB client initialized")
    return _client

def get_db():
    """Get Fundametrics database"""
    global _db
    if _db is None:
        client = get_client()
        _db = client["fundametrics"]
        logger.info("Connected to fundametrics database")
    return _db

# Collection references
def get_companies_col():
    """Companies collection"""
    return get_db()["companies"]

def get_financials_annual_col():
    """Annual financials collection"""
    return get_db()["financials_annual"]

def get_financials_quarterly_col():
    """Quarterly financials collection"""
    return get_db()["financials_quarterly"]

def get_metrics_col():
    """Metrics collection"""
    return get_db()["metrics"]

def get_ownership_col():
    """Ownership collection"""
    return get_db()["ownership"]

def get_trust_metadata_col():
    """Trust metadata collection"""
    return get_db()["trust_metadata"]

def get_trust_reports_col():
    """Trust reports collection (Phase 24)"""
    return get_db()["trust_reports"]

async def init_indexes():
    """
    Create indexes for optimal query performance
    
    This should be run once during initial setup or deployment
    """
    logger.info("Creating MongoDB indexes...")
    
    # Companies collection
    companies = get_companies_col()
    await companies.create_index("symbol", unique=True)
    await companies.create_index("sector")
    await companies.create_index("industry")
    await companies.create_index([("name", TEXT)])
    # Snapshot indices for sorting/filtering (Phase 5)
    await companies.create_index("snapshot.marketCap")
    await companies.create_index("snapshot.pe")
    await companies.create_index("snapshot.roe")
    await companies.create_index("snapshot.roce")
    logger.info("✅ Companies indexes created")

    # Companies Registry collection
    registry = get_db()["companies_registry"]
    await registry.create_index("symbol", unique=True)
    await registry.create_index([("name", TEXT)])
    await registry.create_index("sector")
    logger.info("✅ Companies Registry indexes created")
    
    # Financials Annual collection
    financials_annual = get_financials_annual_col()
    await financials_annual.create_index(
        [("symbol", ASCENDING), ("year", ASCENDING), ("statement_type", ASCENDING)],
        unique=True
    )
    await financials_annual.create_index("symbol")
    logger.info("✅ Financials Annual indexes created")
    
    # Financials Quarterly collection
    financials_quarterly = get_financials_quarterly_col()
    await financials_quarterly.create_index(
        [("symbol", ASCENDING), ("quarter", ASCENDING), ("statement_type", ASCENDING)],
        unique=True
    )
    await financials_quarterly.create_index("symbol")
    logger.info("✅ Financials Quarterly indexes created")
    
    # Metrics collection
    metrics = get_metrics_col()
    await metrics.create_index(
        [("symbol", ASCENDING), ("period", ASCENDING), ("metric_name", ASCENDING)],
        unique=True
    )
    await metrics.create_index("symbol")
    await metrics.create_index("metric_name")
    await metrics.create_index([("period", DESCENDING)])
    logger.info("✅ Metrics indexes created")
    
    # Ownership collection
    ownership = get_ownership_col()
    await ownership.create_index(
        [("symbol", ASCENDING), ("quarter", ASCENDING)],
        unique=True
    )
    await ownership.create_index("symbol")
    logger.info("✅ Ownership indexes created")
    
    # Trust Metadata collection
    trust_metadata = get_trust_metadata_col()
    await trust_metadata.create_index("symbol")
    await trust_metadata.create_index("run_id")
    await trust_metadata.create_index([("run_timestamp", DESCENDING)])
    logger.info("✅ Trust Metadata indexes created")

    # Trust Reports collection (Phase 24)
    trust_reports = get_trust_reports_col()
    await trust_reports.create_index("symbol", unique=True)
    await trust_reports.create_index("run_id")
    await trust_reports.create_index([("generated_at", DESCENDING)])
    logger.info("✅ Trust Reports indexes created")
    
    logger.info("🎉 All MongoDB indexes created successfully")

async def close_db():
    """Close MongoDB connection"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")

async def ping_db() -> bool:
    """
    Ping MongoDB to check connection
    
    Returns:
        bool: True if connected, False otherwise
    """
    try:
        client = get_client()
        await client.admin.command('ping')
        logger.info("MongoDB connection successful")
        return True
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return False
