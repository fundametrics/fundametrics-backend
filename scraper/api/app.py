import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from scraper.api.routes import router
from scraper.api.routes_admin_boost import router as admin_boost_router
from scraper.api.mongo_routes import router as mongo_router  # Phase 22: MongoDB routes
from scraper.api.registry_routes import router as registry_router  # Phase A: Registry + On-Demand
from scraper.api.settings import get_api_settings
from scraper.core.db import init_indexes

app = FastAPI(
    title="Fundametrics API - Phase 25",
    description="MongoDB-powered API with two-layer company system and on-demand ingestion",
    version="2.5.0",
)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup_event():
    # Initialize MongoDB indexes
    try:
        await init_indexes()
    except Exception as e:
        print(f"Index initialization failed: {e}")
        
    # Start Autopilot Scheduler
    try:
        from scraper.core.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"Scheduler startup failed: {e}")


@app.middleware("http")
async def enforce_read_only(request: Request, call_next):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return await call_next(request)

    settings = get_api_settings()

    # Allow POST to admin endpoints and data generation endpoints
    if (
        request.method == "POST"
        and (
            request.url.path in {"/admin/ingest", "/admin/boost"}
            or request.url.path.startswith("/company/") and request.url.path.endswith("/generate")
            or request.url.path.startswith("/admin/company/") and request.url.path.endswith("/generate")
        )
        and settings.ingest_enabled
    ):
        return await call_next(request)

    return JSONResponse(status_code=405, content={"detail": "Fundametrics API is read-only. Use GET endpoints."})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://fundametrics.in",
        "https://www.fundametrics.in",
        "https://fundametrics-frontend.pages.dev",  # Cloudflare Pages
        "https://funda-metrics.pages.dev",  # Legacy (if exists)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Phase A: Registry routes (prioritized for listing)
app.include_router(registry_router, tags=["Registry"])

# Phase 22: MongoDB routes
app.include_router(mongo_router, prefix="/api", tags=["MongoDB"])

# Legacy SQLite routes (fallback)
app.include_router(router, prefix="/api", tags=["SQLite (Legacy)"])
app.include_router(admin_boost_router, tags=["Admin"])

@app.get("/health")
def health():
    return {"status": "ok", "env": os.getenv("ENV", "dev")}
