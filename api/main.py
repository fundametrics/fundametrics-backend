"""
Fundametrics API — FastAPI Application
========================================

Production-ready FastAPI app with:
  - Database initialization on startup
  - APScheduler integration
  - Rate limiting middleware
  - CORS configuration
"""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.endpoints import router as api_router
from scraper.api.mongo_routes import router as mongo_router
from db.manager import init_db
from scraper.core.db import init_indexes, close_db, ping_db

load_dotenv()

# ─── Rate limiter state ──────────────────────────────────────────────
_rate_buckets: dict = defaultdict(lambda: {"tokens": 60.0, "last_refill": time.time()})
_RATE_LIMIT = 60  # requests per minute


# ─── Lifespan (startup/shutdown) ─────────────────────────────────────

_scheduler_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + start scheduler. Shutdown: stop scheduler."""
    global _scheduler_instance

    # 1. Initialize SQL database (Metadata/Legacy)
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./finox_stock_data.db")
    if db_url:
        init_db(db_url)
        print("✅ SQL Database initialized")

        # Create new tables (Watchlist, DailyApiUsage) if they don't exist
        try:
            from db.models import Base
            from db.manager import db_manager

            async def create_tables():
                async with db_manager.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

            await create_tables()
            print("✅ SQL Database tables synced")
        except Exception as e:
            print(f"⚠️  SQL Table sync warning: {e}")
    else:
        print("⚠️  DATABASE_URL not set. SQL features disabled.")

    # 1.1 Initialize MongoDB (New Primary Data Store)
    try:
        if await ping_db():
            await init_indexes()
            print("✅ MongoDB connected and indexes verified")
        else:
            print("❌ MongoDB connection failed")
    except Exception as e:
        print(f"⚠️  MongoDB initialization error: {e}")

    # 2. Start scheduler
    try:
        from scraper.scheduler import start_scheduler
        _scheduler_instance = start_scheduler()
        if _scheduler_instance:
            print("✅ Scheduler started")
    except Exception as e:
        print(f"⚠️  Scheduler not started: {e}")

    yield  # App is running

    # Shutdown
    if _scheduler_instance:
        _scheduler_instance.shutdown(wait=False)
        print("🛑 Scheduler stopped")
    
    await close_db()
    print("🛑 MongoDB connection closed")


# ─── App creation ────────────────────────────────────────────────────

app = FastAPI(
    title="Fundametrics Scraper API",
    description="Internal API for accessing cached Indian Stock Fundamentals with live data, sector analysis, and watchlists.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Rate limiting middleware ─────────────────────────────────────────

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple token-bucket rate limiter: 60 req/min per IP."""
    client_ip = request.client.host if request.client else "unknown"

    # Skip rate limiting for docs
    if request.url.path in ("/docs", "/openapi.json", "/redoc", "/"):
        return await call_next(request)

    bucket = _rate_buckets[client_ip]
    now = time.time()
    elapsed = now - bucket["last_refill"]

    # Refill
    bucket["tokens"] = min(_RATE_LIMIT, bucket["tokens"] + elapsed * (_RATE_LIMIT / 60.0))
    bucket["last_refill"] = now

    if bucket["tokens"] < 1:
        return Response(
            content='{"detail":"Rate limit exceeded. Max 60 requests/minute."}',
            status_code=429,
            media_type="application/json",
        )

    bucket["tokens"] -= 1
    return await call_next(request)


# ─── Routes ───────────────────────────────────────────────────────────

# Phase 22: Register MongoDB-first routes
# This ensures that for overlapping paths like /stocks/{symbol}, we use the MongoDB implementation
app.include_router(mongo_router, prefix="/api/v1")

# Register Legacy / Tooling routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Welcome to Fundametrics Scraper API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "stocks": "/api/v1/stocks",
            "live": "/api/v1/stocks/{symbol}/live",
            "cache_status": "/api/v1/stocks/{symbol}/cache-status",
            "sector_summary": "/api/v1/sectors/{sector}/summary",
            "vs_peers": "/api/v1/stocks/{symbol}/vs-peers",
            "watchlist": "/api/v1/users/{user_id}/watchlist",
            "scheduler": "/api/v1/admin/scheduler/status",
            "coverage": "/api/v1/admin/coverage",
        }
    }


@app.get("/health")
async def health():
    """Operational heartbeat."""
    from scraper.scheduler import get_scheduler_status
    sched = get_scheduler_status()
    return {
        "status": "healthy",
        "scheduler_running": sched.get("is_running", False),
        "last_scrape": sched.get("last_runs", {}).get("nightly_scrape", {}).get("timestamp"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
