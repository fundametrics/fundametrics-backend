"""
Two-Layer Company System API Routes
Phase A: Registry + On-Demand Data Generation
IMPORTANT: This is NOT analysis - we generate structured public data
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, Query
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import asyncio
from scraper.core.db import get_db
from scraper.core.mongo_repository import MongoRepository
from scraper.core.ingestion import ingest_symbol
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
registry_router = APIRouter(prefix="/api") # For Step 5 Search

# Safety: Prevent VPS overload
MAX_ANALYSES_PER_DAY = 20

# In-memory lock to prevent duplicate ingestion
ingestion_locks = set()
global_ingestion_lock = asyncio.Lock()

# Daily counter (resets at midnight)
daily_counter = {"date": None, "count": 0}

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "fundametrics18")
ALLOW_ANALYZE = os.getenv("ALLOW_ANALYZE", "true").lower() == "true"


def verify_admin(x_admin_token: str = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Admin only")


def check_daily_limit():
    """Check if daily analysis limit is reached"""
    today = date.today().isoformat()
    
    # Reset counter if new day
    if daily_counter["date"] != today:
        daily_counter["date"] = today
        daily_counter["count"] = 0
    
    # Check limit
    if daily_counter["count"] >= MAX_ANALYSES_PER_DAY:
        return False
    
    return True


def increment_daily_counter():
    """Increment daily analysis counter"""
    today = date.today().isoformat()
    
    if daily_counter["date"] != today:
        daily_counter["date"] = today
        daily_counter["count"] = 0
    
    daily_counter["count"] += 1


# In-memory cache for registry endpoint (60s TTL, max 50 entries)
registry_cache = {}
REGISTRY_CACHE_TTL = 60  # Reduced to 1 minute for better consistency
REGISTRY_CACHE_MAX_SIZE = 50  # Prevent memory leaks


def clear_registry_cache():
    """Clear the registry cache to reflect status changes immediately"""
    global registry_cache
    registry_cache = {}
    logger.info("Registry cache cleared globally (local process)")


@router.get("/companies/registry")
async def list_company_registry(
    skip: int = 0, 
    limit: int = 50,
    status: Optional[str] = Query(None, description="Filter: 'pending' to show only non-ingested companies"),
    refresh: Optional[bool] = Query(None, description="Bypass cache for real-time updates")
):
    """
    List companies from registry with availability status.
    If status='pending', only show companies NOT yet in the 'companies' collection.
    """
    try:
        # Check cache (only for non-filtered requests to keep it simple)
        cache_key = f"{skip}:{limit}:{status}"
        now = datetime.utcnow().timestamp()
        
        # Admin can bypass cache
        if refresh:
            clear_registry_cache()
        elif cache_key in registry_cache:
            cached_data, cached_time = registry_cache[cache_key]
            if now - cached_time < REGISTRY_CACHE_TTL:
                return cached_data
        
        db = get_db()
        registry_col = db["companies_registry"]
        companies_col = db["companies"]
        mongo_repo = MongoRepository(db)
        
        query = {}
        if status == "pending":
            # Find all symbols already analyzed
            analyzed_cursor = companies_col.find({}, {"symbol": 1, "_id": 0})
            analyzed_symbols = [doc["symbol"] async for doc in analyzed_cursor]
            query = {"symbol": {"$nin": analyzed_symbols}}
            
        # Get registry companies - Sort by Priority (Phase 16), then Market Cap, then symbol
        registry_cursor = registry_col.find(
            query,
            {"_id": 0, "symbol": 1, "name": 1, "sector": 1, "last_failure": 1}
        ).sort([
            ("snapshot.priority", -1), 
            ("snapshot.marketCap", -1), 
            ("symbol", 1)
        ]).skip(skip).limit(limit)
        
        registry_companies = await registry_cursor.to_list(length=limit)
        symbols = [c["symbol"] for c in registry_companies]
        
        # Fetch detailed metrics for those already ingested (if any in this slice)
        detailed_data = await mongo_repo.get_companies_detail(symbols)
        detailed_map = {d["symbol"]: d for d in detailed_data}
        
        # Build response
        result = []
        for company in registry_companies:
            symbol = company["symbol"]
            detail = detailed_map.get(symbol)
            
            # Since we might be filtering for pending, status check is still useful
            if detail:
                item_status = "available"
            elif symbol in ingestion_locks:
                item_status = "generating"
            elif company.get("last_failure"):
                item_status = "failed"
            else:
                item_status = "not_available"
            
            result.append({
                "symbol": symbol,
                "name": company["name"],
                "sector": detail.get("sector") if detail else company.get("sector", "General"),
                "status": item_status,
                "lastFailure": company.get("last_failure"),
                "marketCap": detail.get("marketCap") if detail else None,
                "pe": detail.get("pe") if detail else None,
                "roe": detail.get("roe") if detail else None,
                "roce": detail.get("roce") if detail else None,
                "debt": detail.get("debt") if detail else None
            })
        
        total = await registry_col.count_documents(query)
        
        response = {
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(result),
            "companies": result
        }
        
        # Cache management
        if len(registry_cache) >= REGISTRY_CACHE_MAX_SIZE:
            oldest_key = min(registry_cache.keys(), key=lambda k: registry_cache[k][1])
            del registry_cache[oldest_key]
        
        registry_cache[cache_key] = (response, now)
        return response
    
    except Exception as e:
        logger.error(f"Failed to fetch registry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch companies: {str(e)}")


@router.get("/company/{symbol}/status")
async def get_company_status(symbol: str):
    """
    Check if structured company data is available
    Returns: {status: 'available' | 'not_available' | 'generating'}
    """
    try:
        # Check if currently being generated
        if symbol in ingestion_locks:
            return {
                "status": "generating",
                "message": "Structured data is being generated"
            }
        
        # Check if data already exists
        db = get_db()
        companies_col = db["companies"]
        company = await companies_col.find_one({"symbol": symbol})
        
        if company:
            return {
                "status": "available",
                "message": "Structured company data is available"
            }
        
        # Check if in registry
        registry_col = db["companies_registry"]
        registry_entry = await registry_col.find_one({"symbol": symbol})
        
        if registry_entry:
            return {
                "status": "not_available",
                "message": "Structured data has not been generated yet",
                "name": registry_entry.get("name"),
                "sector": registry_entry.get("sector")
            }
        
        return {
            "status": "not_found",
            "message": "Company not in registry"
        }
    
    except Exception as e:
        logger.error(f"Failed to check status for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_data_generation_task(symbol: str):
    """Background task to generate structured company data"""
    try:
        # Run ingestion (data generation) with global lock to prevent VPS overload
        async with global_ingestion_lock:
            logger.info(f"STARTING global-locked data generation for {symbol}")
            result = await ingest_symbol(symbol)
        
        # Update registry and Save data
        db = get_db()
        companies_col = db["companies"]
        registry_col = db["companies_registry"]
        
        # Save structured data
        storage_payload = result.get("storage_payload")
        if storage_payload:
            await companies_col.update_one(
                {"symbol": symbol},
                {"$set": storage_payload},
                upsert=True
            )
            
        await registry_col.update_one(
            {"symbol": symbol},
            {"$set": {
                "is_analyzed": True,
                "data_generated_at": datetime.utcnow().isoformat()
            }}
        )
        
        logger.info(f"SUCCESS: Data generation complete for {symbol}")
        
    except Exception as e:
        logger.error(f"FAILURE: Data generation failed for {symbol}: {str(e)}")
        # Record failure in registry
        try:
            db = get_db()
            registry_col = db["companies_registry"]
            await registry_col.update_one(
                {"symbol": symbol},
                {"$set": {
                    "last_failure": datetime.utcnow().isoformat(),
                    "is_analyzed": False
                }}
            )
        except:
            pass
    
    finally:
        # Release lock
        if symbol in ingestion_locks:
            ingestion_locks.remove(symbol)
        
        # Clear cache to reflect "Available" status
        clear_registry_cache()


@router.post("/company/{symbol}/generate")
async def generate_company_data(symbol: str, background_tasks: BackgroundTasks, x_admin_token: str = Header(None)):
    """
    Generate structured public data for a company (user-facing endpoint)
    Returns: {status: 'queued' | 'already_available' | 'already_generating' | 'limit_reached'}
    """
    # Check if public analysis is disabled
    if not ALLOW_ANALYZE:
        verify_admin(x_admin_token)
    
    try:
        # Check daily limit
        if not check_daily_limit():
            return {
                "status": "limit_reached",
                "message": "Data generation limit reached for today. Please try again tomorrow.",
                "limit": MAX_ANALYSES_PER_DAY
            }
        
        # Check if already being generated
        if symbol in ingestion_locks:
            return {
                "status": "already_generating",
                "message": "Data generation already in progress for this company"
            }
        
        # Check if data already exists
        db = get_db()
        companies_col = db["companies"]
        existing = await companies_col.find_one({"symbol": symbol})
        
        if existing:
            return {
                "status": "already_available",
                "message": "Structured company data is already available"
            }
        
        # Check if in registry
        registry_col = db["companies_registry"]
        registry_entry = await registry_col.find_one({"symbol": symbol})
        
        if not registry_entry:
            raise HTTPException(status_code=404, detail="Company not found in registry")
        
        # Acquire lock
        ingestion_locks.add(symbol)
        
        # Increment counter
        increment_daily_counter()
        
        # Queue background task
        background_tasks.add_task(run_data_generation_task, symbol)
        
        # Clear cache to reflect "Generating" status
        clear_registry_cache()
        
        return {
            "status": "queued",
            "message": "Generating structured company data. This usually takes 1-2 minutes.",
            "symbol": symbol
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue data generation for {symbol}: {str(e)}")
        if symbol in ingestion_locks:
            ingestion_locks.remove(symbol)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/company/{symbol}/generate")
async def admin_generate_company_data(symbol: str, background_tasks: BackgroundTasks, x_admin_token: str = Header(None)):
    """
    Admin-only endpoint to generate company data (bypasses daily limit)
    For team use only - same backend, no duplication
    """
    verify_admin(x_admin_token)
    
    try:
        # Check if already being generated
        if symbol in ingestion_locks:
            return {
                "status": "already_generating",
                "message": "Data generation already in progress"
            }
        
        # Check if data already exists
        db = get_db()
        companies_col = db["companies"]
        existing = await companies_col.find_one({"symbol": symbol})
        
        if existing:
            return {
                "status": "already_available",
                "message": "Data already exists"
            }
        
        # Acquire lock
        ingestion_locks.add(symbol)
        
        # Queue background task (same function, no duplication)
        background_tasks.add_task(run_data_generation_task, symbol)
        
        # Clear cache to reflect "Generating" status
        clear_registry_cache()
        
        return {
            "status": "queued",
            "message": f"Admin: Data generation started for {symbol}",
            "symbol": symbol
        }
    
    except Exception as e:
        logger.error(f"Admin generation failed for {symbol}: {str(e)}")
        if symbol in ingestion_locks:
            ingestion_locks.remove(symbol)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/stats")
async def get_admin_stats():
    """Admin endpoint to check daily usage stats"""
    db = get_db()
    registry_col = db["companies_registry"]
    companies_col = db["companies"]
    
    total_registry = await registry_col.count_documents({})
    total_generated = await companies_col.count_documents({})
    currently_generating = len(ingestion_locks)
    
    return {
        "total_in_registry": total_registry,
        "total_data_generated": total_generated,
        "currently_generating": currently_generating,
        "daily_limit": MAX_ANALYSES_PER_DAY,
        "today_generated": daily_counter.get("count", 0),
        "today_date": daily_counter.get("date"),
        "remaining_today": max(0, MAX_ANALYSES_PER_DAY - daily_counter.get("count", 0))
    }


@registry_router.get("/search")
@router.get("/search/registry")
async def search_registry(q: str = ""):
    """
    Search companies in the registry (includes non-ingested companies)
    Returns: List of companies matching the search query
    """
    if not q.strip():
        return {
            "query": "",
            "results": [],
            "disclaimer": "Search results are informational only."
        }
    
    try:
        db = get_db()
        registry_col = db["companies_registry"]
        companies_col = db["companies"]
        
        # Search in registry (case-insensitive)
        search_regex = {"$regex": q.strip(), "$options": "i"}
        registry_results = await registry_col.find(
            {
                "$or": [
                    {"symbol": search_regex},
                    {"name": search_regex}
                ]
            },
            {"_id": 0, "symbol": 1, "name": 1, "sector": 1}
        ).limit(25).to_list(length=25)
        
        # Get analyzed symbols to determine status
        analyzed_cursor = companies_col.find({}, {"symbol": 1, "_id": 0})
        analyzed_symbols = {doc["symbol"] async for doc in analyzed_cursor}
        
        # Add status to results
        results = []
        for company in registry_results:
            symbol = company["symbol"]
            results.append({
                "symbol": symbol,
                "name": company["name"],
                "sector": company.get("sector", "General"),
                "status": "available" if symbol in analyzed_symbols else "not_available"
            })
        
        return {
            "query": q,
            "results": results,
            "disclaimer": "Search results are informational only."
        }
    
    except Exception as e:
        logger.error(f"Registry search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
