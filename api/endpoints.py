"""
Fundametrics API Endpoints
===========================

Complete REST API surface including:
  - Stock fundamentals (with stale-while-revalidate caching)
  - Live market data via yfinance
  - Sector comparison
  - User watchlists
  - Admin: scheduler status, coverage reports
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete, and_

from db.manager import db_manager
from db.models import (
    Company, CompanyFact, ComputedMetric, FinancialYearly,
    Management, ScrapeLog, Watchlist,
)
from api.schemas import (
    CompanyRead, FactRead, FundametricsMetricRead, FinancialMetric,
    ManagementRead, StockDetailRead, ScrapeLogRead,
    LiveDataResponse, CacheStatusResponse,
    SectorSummaryResponse, PeerComparisonResponse,
    WatchlistAdd, WatchlistUpdate, WatchlistItem, WatchlistResponse,
    SchedulerStatusResponse, CoverageResponse,
)

router = APIRouter()

# ─── In-memory caches for stale-while-revalidate ────────────────────
_fundamentals_cache: Dict[str, Dict[str, Any]] = {}
_live_price_cache: Dict[str, Dict[str, Any]] = {}
_refreshing_symbols: set = set()

# Config defaults (overridden from settings.yaml if available)
_FUNDAMENTALS_TTL_HOURS = 24
_LIVE_PRICE_TTL_SECONDS = 30

# ─── Rate limiter (in-memory token bucket) ───────────────────────────
_rate_buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"tokens": 60, "last_refill": time.time()})
_RATE_LIMIT_PER_MINUTE = 60


def _check_rate_limit(client_ip: str) -> bool:
    """Token bucket rate limiter. Returns True if allowed."""
    bucket = _rate_buckets[client_ip]
    now = time.time()
    elapsed = now - bucket["last_refill"]

    # Refill tokens
    bucket["tokens"] = min(_RATE_LIMIT_PER_MINUTE, bucket["tokens"] + elapsed * (_RATE_LIMIT_PER_MINUTE / 60))
    bucket["last_refill"] = now

    if bucket["tokens"] >= 1:
        bucket["tokens"] -= 1
        return True
    return False


# ─── DB dependency ───────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with db_manager.session_factory() as session:
        yield session


# ═══════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS (enhanced)
# ═══════════════════════════════════════════════════════════════════

@router.get("/stocks", response_model=List[CompanyRead])
async def list_stocks(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    sector: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all companies with optional search and sector filter."""
    stmt = select(Company)
    if search:
        stmt = stmt.where(
            (Company.name.ilike(f"%{search}%")) | (Company.symbol.ilike(f"%{search}%"))
        )
    if sector and sector != "all":
        stmt = stmt.where(Company.sector == sector)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stocks/{symbol}", response_model=StockDetailRead)
async def get_stock_detail(
    symbol: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Get stock fundamentals with stale-while-revalidate caching.

    Returns cached data immediately. If stale (>24h), triggers background refresh.
    Response includes `cache_status` field.
    """
    symbol = symbol.upper()

    # 1. Fetch from DB
    stmt = select(Company).where(Company.symbol == symbol)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # 2. Latest Facts
    f_stmt = select(CompanyFact).where(CompanyFact.company_id == company.id).order_by(desc(CompanyFact.snapshot_date)).limit(1)
    f_result = await db.execute(f_stmt)
    latest_f = f_result.scalar_one_or_none()

    # 3. Historical Facts
    h_stmt = select(CompanyFact).where(CompanyFact.company_id == company.id).order_by(desc(CompanyFact.snapshot_date)).offset(1).limit(5)
    h_result = await db.execute(h_stmt)
    history_f = h_result.scalars().all()

    # 4. Computed Metrics
    m_stmt = select(ComputedMetric).where(ComputedMetric.company_id == company.id).order_by(desc(ComputedMetric.period))
    m_result = await db.execute(m_stmt)
    metrics = m_result.scalars().all()

    # 5. Yearly Financials
    fin_stmt = select(FinancialYearly).where(FinancialYearly.company_id == company.id).order_by(desc(FinancialYearly.fiscal_year))
    fin_result = await db.execute(fin_stmt)
    financials = fin_result.scalars().all()
    grouped_financials: Dict[str, list] = {}
    for fin in financials:
        s_type = fin.statement_type
        grouped_financials.setdefault(s_type, []).append(fin)

    # 6. Management
    mg_stmt = select(Management).where(Management.company_id == company.id)
    mg_result = await db.execute(mg_stmt)
    mgmt = mg_result.scalars().all()

    # 7. Check staleness & trigger background refresh
    _check_and_refresh(symbol, background_tasks)

    return {
        "company": company,
        "latest_facts": latest_f,
        "historical_facts": history_f,
        "fundametrics_metrics": metrics,
        "yearly_financials": grouped_financials,
        "management": mgmt,
    }


def _check_and_refresh(symbol: str, background_tasks: BackgroundTasks):
    """Stale-while-revalidate: trigger background scrape if data is old."""
    cached = _fundamentals_cache.get(symbol)
    if cached:
        age = datetime.now(timezone.utc) - cached.get("fetched_at", datetime.min.replace(tzinfo=timezone.utc))
        if age > timedelta(hours=_FUNDAMENTALS_TTL_HOURS) and symbol not in _refreshing_symbols:
            _refreshing_symbols.add(symbol)
            background_tasks.add_task(_background_refresh, symbol)

    # Also check live price staleness
    live = _live_price_cache.get(symbol)
    if live:
        age = datetime.now(timezone.utc) - live.get("fetched_at", datetime.min.replace(tzinfo=timezone.utc))
        if age > timedelta(seconds=_LIVE_PRICE_TTL_SECONDS) and symbol not in _refreshing_symbols:
            background_tasks.add_task(_background_live_refresh, symbol)


async def _background_refresh(symbol: str):
    """Background task: re-scrape a symbol's fundamentals."""
    try:
        from scraper.main import run_scraper
        run_scraper(symbol=symbol, trendlyne=False, persist_runs=True)
        _fundamentals_cache[symbol] = {"fetched_at": datetime.now(timezone.utc)}
    except Exception:
        pass
    finally:
        _refreshing_symbols.discard(symbol)


async def _background_live_refresh(symbol: str):
    """Background task: refresh live price fields only."""
    try:
        from scraper.sources.yfinance_source import get_live_data
        data = get_live_data(symbol)
        _live_price_cache[symbol] = {"data": data, "fetched_at": datetime.now(timezone.utc)}
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
# PHASE 1: LIVE DATA ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.get("/stocks/{symbol}/live", response_model=LiveDataResponse)
async def get_stock_live(symbol: str, request: Request):
    """
    Fetch real-time market data directly from yfinance. No caching, no DB write.
    """
    if not _check_rate_limit(request.client.host if request.client else "unknown"):
        raise HTTPException(status_code=429, detail="Rate limit exceeded (60 req/min)")

    try:
        from scraper.sources.yfinance_source import get_live_data
        data = get_live_data(symbol.upper())
        return data
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch live data: {exc}")


# ═══════════════════════════════════════════════════════════════════
# PHASE 2: CACHE STATUS ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.get("/stocks/{symbol}/cache-status", response_model=CacheStatusResponse)
async def get_cache_status(symbol: str):
    """Return cache age and next refresh schedule for a symbol."""
    symbol = symbol.upper()
    cached = _fundamentals_cache.get(symbol)
    live = _live_price_cache.get(symbol)

    if not cached:
        # Check JSON repository
        try:
            from scraper.core.repository import DataRepository
            repo = DataRepository()
            latest = repo.get_latest(symbol)
            if latest:
                ts = latest.get("run_timestamp") or latest.get("fundametrics_response", {}).get("metadata", {}).get("run_timestamp")
                if ts:
                    cached_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - cached_at).total_seconds()
                    is_stale = age > _FUNDAMENTALS_TTL_HOURS * 3600
                    status = "stale_refreshing" if (is_stale and symbol in _refreshing_symbols) else ("stale" if is_stale else "fresh")
                    return CacheStatusResponse(
                        symbol=symbol,
                        cache_status=status,
                        cached_at=ts,
                        age_seconds=round(age, 1),
                        age_human=_human_age(age),
                        next_refresh_at=(cached_at + timedelta(hours=_FUNDAMENTALS_TTL_HOURS)).isoformat() if not is_stale else "pending",
                        ttl_hours=_FUNDAMENTALS_TTL_HOURS,
                        live_price_age_seconds=None,
                    )
        except Exception:
            pass

        return CacheStatusResponse(symbol=symbol, cache_status="missing")

    fetched_at = cached["fetched_at"]
    age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    is_stale = age > _FUNDAMENTALS_TTL_HOURS * 3600
    status = "stale_refreshing" if (is_stale and symbol in _refreshing_symbols) else ("stale" if is_stale else "fresh")

    live_age = None
    if live:
        live_age = (datetime.now(timezone.utc) - live["fetched_at"]).total_seconds()

    return CacheStatusResponse(
        symbol=symbol,
        cache_status=status,
        cached_at=fetched_at.isoformat(),
        age_seconds=round(age, 1),
        age_human=_human_age(age),
        next_refresh_at=(fetched_at + timedelta(hours=_FUNDAMENTALS_TTL_HOURS)).isoformat() if not is_stale else "pending",
        ttl_hours=_FUNDAMENTALS_TTL_HOURS,
        live_price_age_seconds=round(live_age, 1) if live_age else None,
    )


def _human_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h"
    return f"{seconds / 86400:.1f}d"


# ═══════════════════════════════════════════════════════════════════
# PHASE 5: SECTOR COMPARISON ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

_DEFAULT_METRICS = ["pe_ratio", "roe", "roce", "debt_to_equity", "pb_ratio"]



@router.get("/sectors")
async def get_sectors(db: AsyncSession = Depends(get_db)):
    """List all unique sectors."""
    stmt = select(Company.sector).where(Company.sector.isnot(None)).distinct()
    result = await db.execute(stmt)
    sectors = [row[0] for row in result.all()]
    return sorted(sectors)

@router.get("/sectors/{sector_name}/summary")
async def get_sector_summary(sector_name: str, db: AsyncSession = Depends(get_db)):
    """Top metrics and stats for a sector."""
    # Find all symbols in this sector
    stmt = select(Company.symbol).where(Company.sector.ilike(f"%{sector_name}%"))
    result = await db.execute(stmt)
    symbols = [row[0] for row in result.all()]

    if not symbols:
        raise HTTPException(status_code=404, detail=f"No companies found in sector '{sector_name}'")

    from scraper.core.analytics.sector_engine import get_cached_sector_summary
    summary = get_cached_sector_summary(sector_name, symbols, _DEFAULT_METRICS)
    return summary


@router.get("/stocks/{symbol}/vs-peers")
async def compare_vs_peers(symbol: str, db: AsyncSession = Depends(get_db)):
    """Compare a stock against its sector peer group."""
    symbol = symbol.upper()

    # Find the company's sector
    stmt = select(Company).where(Company.symbol == symbol)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    if not company.sector:
        raise HTTPException(status_code=404, detail="Sector not available for this stock")

    # Find peers in same sector
    peer_stmt = select(Company.symbol).where(
        Company.sector == company.sector,
        Company.symbol != symbol,
        Company.is_active == True,
    ).limit(20)
    peer_result = await db.execute(peer_stmt)
    peer_symbols = [row[0] for row in peer_result.all()]

    from scraper.core.analytics.sector_engine import compute_peer_comparison
    comparison = compute_peer_comparison(symbol, peer_symbols, _DEFAULT_METRICS)
    return comparison


# ═══════════════════════════════════════════════════════════════════
# PHASE 6: WATCHLIST ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.post("/users/{user_id}/watchlist")
async def add_to_watchlist(user_id: str, payload: WatchlistAdd, db: AsyncSession = Depends(get_db)):
    """Add a symbol to a user's watchlist."""
    # Check if already exists
    stmt = select(Watchlist).where(and_(Watchlist.user_id == user_id, Watchlist.symbol == payload.symbol.upper()))
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"{payload.symbol} already in watchlist")

    entry = Watchlist(
        user_id=user_id,
        symbol=payload.symbol.upper(),
        notes=payload.notes,
    )
    db.add(entry)
    await db.commit()

    return await get_watchlist(user_id, db)


@router.delete("/users/{user_id}/watchlist/{symbol}")
async def remove_from_watchlist(user_id: str, symbol: str, db: AsyncSession = Depends(get_db)):
    """Remove a symbol from a user's watchlist."""
    stmt = delete(Watchlist).where(and_(Watchlist.user_id == user_id, Watchlist.symbol == symbol.upper()))
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")
    return {"status": "removed", "symbol": symbol.upper()}


@router.get("/users/{user_id}/watchlist", response_model=WatchlistResponse)
async def get_watchlist(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get all watchlisted symbols with their latest cached metrics."""
    stmt = select(Watchlist).where(Watchlist.user_id == user_id).order_by(desc(Watchlist.added_at))
    result = await db.execute(stmt)
    entries = result.scalars().all()

    items = []
    for entry in entries:
        item = WatchlistItem(
            symbol=entry.symbol,
            added_at=entry.added_at,
            notes=entry.notes,
        )
        # Try to hydrate with live cache
        live = _live_price_cache.get(entry.symbol, {}).get("data", {})
        if live:
            item.price = live.get("price")
            item.pe_ratio = live.get("pe_ratio")
            prev = live.get("previous_close")
            if item.price and prev and prev > 0:
                item.change_1d = round(((item.price - prev) / prev) * 100, 2)
        items.append(item)

    return WatchlistResponse(user_id=user_id, symbols=items, total=len(items))


@router.patch("/users/{user_id}/watchlist/{symbol}")
async def update_watchlist_notes(user_id: str, symbol: str, payload: WatchlistUpdate, db: AsyncSession = Depends(get_db)):
    """Update notes for a watchlist entry."""
    stmt = select(Watchlist).where(and_(Watchlist.user_id == user_id, Watchlist.symbol == symbol.upper()))
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail=f"{symbol} not found in watchlist")

    entry.notes = payload.notes
    await db.commit()
    return {"status": "updated", "symbol": symbol.upper(), "notes": payload.notes}


# ═══════════════════════════════════════════════════════════════════
# PHASE 7: ADMIN ENDPOINTS (Scheduler + Rate Limiting)
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status():
    """Show scheduler state: next runs, last timestamps, failure counts."""
    from scraper.scheduler import get_scheduler_status
    return get_scheduler_status()


# ═══════════════════════════════════════════════════════════════════
# PHASE 8: COVERAGE / QUALITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/admin/coverage")
async def get_coverage():
    """
    Return data quality coverage report:
    - Total symbols scraped
    - Completeness score distribution
    - Lowest completeness symbols
    - Symbols with active anomaly flags
    """
    from scraper.core.repository import DataRepository
    repo = DataRepository()
    symbols = repo.list_symbols()

    buckets = {"0-25%": [], "25-50%": [], "50-75%": [], "75-100%": []}
    lowest = []
    anomaly_symbols = []

    for sym in symbols:
        run = repo.get_latest(sym)
        if not run:
            continue

        quality = run.get("quality", {})
        score = quality.get("completeness_score", 0.0)
        anomalies = quality.get("anomaly_flags", [])

        if score < 0.25:
            buckets["0-25%"].append(sym)
        elif score < 0.50:
            buckets["25-50%"].append(sym)
        elif score < 0.75:
            buckets["50-75%"].append(sym)
        else:
            buckets["75-100%"].append(sym)

        lowest.append({"symbol": sym, "completeness_score": round(score, 3)})

        if anomalies:
            anomaly_symbols.append({"symbol": sym, "anomalies": anomalies})

    # Sort lowest by score ascending, take top 20
    lowest.sort(key=lambda x: x["completeness_score"])

    distribution = [
        {"range_label": k, "count": len(v), "symbols": v[:10]}
        for k, v in buckets.items()
    ]

    return {
        "total_symbols": len(symbols),
        "distribution": distribution,
        "lowest_completeness": lowest[:20],
        "anomaly_symbols": anomaly_symbols[:20],
    }


# ═══════════════════════════════════════════════════════════════════
# LEGACY ALIASES
# ═══════════════════════════════════════════════════════════════════

@router.get("/companies", response_model=List[CompanyRead])
async def list_companies_alias(
    skip: int = 0, limit: int = 100, search: Optional[str] = None,
    sector: Optional[str] = None, db: AsyncSession = Depends(get_db),
):
    """Alias for /stocks to support frontend legacy route."""
    return await list_stocks(skip, limit, search, sector, db)


@router.get("/logs", response_model=List[ScrapeLogRead])
async def get_scrape_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent scrape logs for monitoring."""
    stmt = select(ScrapeLog).order_by(desc(ScrapeLog.created_at)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


class CompareRequest(BaseModel):
    metric_a: Dict[str, Any]
    metric_b: Dict[str, Any]


@router.post("/compare/check")
async def check_comparison_eligibility(payload: CompareRequest):
    """Validates if two metrics can be compared safely."""
    from scraper.core.compare import can_compare
    return can_compare(payload.metric_a, payload.metric_b)


@router.get("/indices/prices")
async def get_indices_prices():
    """Live market indices via yfinance."""
    try:
        from scraper.sources.yfinance_source import get_live_data
        import yfinance as yf

        indices = {
            "nifty50": ("^NSEI", "NIFTY 50"),
            "sensex": ("^BSESN", "SENSEX"),
            "niftybank": ("^NSEBANK", "BANK NIFTY"),
            "niftyit": ("^CNXIT", "NIFTY IT"),
        }
        result = []
        for idx_id, (ticker_sym, label) in indices.items():
            try:
                t = yf.Ticker(ticker_sym)
                info = t.info or {}
                price = info.get("regularMarketPrice") or info.get("previousClose", 0)
                prev = info.get("previousClose", 0)
                change = round(price - prev, 2) if price and prev else 0
                change_pct = round((change / prev) * 100, 2) if prev else 0
                result.append({
                    "id": idx_id, "label": label, "price": price,
                    "change": change, "changePercent": change_pct, "symbol": ticker_sym,
                })
            except Exception:
                result.append({"id": idx_id, "label": label, "price": 0, "change": 0, "changePercent": 0, "symbol": ticker_sym})
        return result
    except ImportError:
        return []
