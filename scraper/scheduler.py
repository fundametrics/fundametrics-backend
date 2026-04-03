"""
Fundametrics Production Scheduler
===================================

APScheduler-based job orchestration for automated data collection:
  - Nightly full scrape (11 PM IST)
  - Live price refresh (every 5 min during market hours)
  - Weekly shareholding update (Sunday 6 AM IST)
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.utils.logger import get_logger

log = get_logger(__name__)

# Track scheduler state
_scheduler_state: Dict[str, Any] = {
    "started_at": None,
    "last_runs": {},
    "failure_counts": defaultdict(int),
    "skipped_symbols": set(),
    "is_running": False,
}

_MAX_CONSECUTIVE_FAILURES = 3


def load_nifty500_symbols() -> List[str]:
    """Load symbol list from config/nifty500.csv or fallback to stock_symbols.txt."""
    csv_path = Path("config/nifty500.csv")
    if csv_path.exists():
        symbols = []
        for line in csv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("Symbol"):
                # Handle CSV: take first column
                sym = line.split(",")[0].strip().upper()
                if sym:
                    symbols.append(sym)
        if symbols:
            return symbols

    # Fallback to stock_symbols.txt
    txt_path = Path("config/stock_symbols.txt")
    if txt_path.exists():
        return [
            line.strip().upper()
            for line in txt_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    # Default minimal list
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK"]


def _nightly_full_scrape():
    """Scrape all symbols via Screener + yfinance (rate-limited)."""
    job_id = str(uuid.uuid4())[:8]
    symbols = load_nifty500_symbols()
    log.info("Nightly scrape starting", job_id=job_id, symbol_count=len(symbols))

    start = time.time()
    success_count = 0
    fail_count = 0

    for sym in symbols:
        # Skip if too many consecutive failures
        if _scheduler_state["failure_counts"][sym] >= _MAX_CONSECUTIVE_FAILURES:
            _scheduler_state["skipped_symbols"].add(sym)
            continue

        try:
            from scraper.main import run_scraper
            run_scraper(symbol=sym, trendlyne=False, persist_runs=True)
            success_count += 1
            _scheduler_state["failure_counts"][sym] = 0
            time.sleep(3)  # Rate limit: 1 symbol per 3 seconds
        except Exception as exc:
            fail_count += 1
            _scheduler_state["failure_counts"][sym] += 1
            log.warning("Nightly scrape failed for symbol", symbol=sym, error=str(exc))

    duration = round(time.time() - start, 1)
    _scheduler_state["last_runs"]["nightly_scrape"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "success": success_count,
        "failed": fail_count,
        "duration_seconds": duration,
    }
    log.info("Nightly scrape complete", job_id=job_id, success=success_count, failed=fail_count, duration=duration)


def _live_price_refresh():
    """Refresh live prices for watched symbols via yfinance."""
    job_id = str(uuid.uuid4())[:8]

    # Only refresh symbols that have watchers (from watchlist) or recently accessed
    symbols = load_nifty500_symbols()[:50]  # Top 50 for live refresh
    log.info("Live price refresh starting", job_id=job_id, symbol_count=len(symbols))

    start = time.time()
    success_count = 0

    for sym in symbols:
        try:
            from scraper.sources.yfinance_source import get_live_data
            get_live_data(sym)
            success_count += 1
        except Exception:
            pass  # Non-critical, skip silently

    duration = round(time.time() - start, 1)
    _scheduler_state["last_runs"]["live_price_refresh"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "refreshed": success_count,
        "duration_seconds": duration,
    }
    log.info("Live price refresh complete", job_id=job_id, refreshed=success_count, duration=duration)


def _weekly_shareholding_update():
    """Update shareholding via NSE API for all symbols."""
    job_id = str(uuid.uuid4())[:8]
    symbols = load_nifty500_symbols()
    log.info("Weekly shareholding update starting", job_id=job_id, symbol_count=len(symbols))

    start = time.time()
    success_count = 0

    for sym in symbols:
        try:
            from scraper.sources.nse_source import get_shareholding
            get_shareholding(sym, force_refresh=True)
            success_count += 1
            time.sleep(2)  # NSE rate limiting
        except Exception:
            pass

    duration = round(time.time() - start, 1)
    _scheduler_state["last_runs"]["weekly_shareholding"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
        "updated": success_count,
        "duration_seconds": duration,
    }
    log.info("Weekly shareholding update complete", job_id=job_id, updated=success_count, duration=duration)


def create_scheduler():
    """Create and configure the APScheduler instance."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        log.warning("APScheduler not installed, scheduler disabled")
        return None

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    # 1. Nightly full scrape: 11 PM IST
    scheduler.add_job(
        _nightly_full_scrape,
        CronTrigger(hour=23, minute=0, timezone="Asia/Kolkata"),
        id="nightly_full_scrape",
        name="Nightly Full Scrape",
        max_instances=1,
        misfire_grace_time=3600,
    )

    # 2. Live price refresh: every 5 minutes during market hours (9:15 AM - 3:30 PM IST, Mon-Fri)
    scheduler.add_job(
        _live_price_refresh,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="*/5",
            timezone="Asia/Kolkata",
        ),
        id="live_price_refresh",
        name="Live Price Refresh",
        max_instances=1,
        misfire_grace_time=300,
    )

    # 3. Weekly shareholding update: Sunday 6 AM IST
    scheduler.add_job(
        _weekly_shareholding_update,
        CronTrigger(day_of_week="sun", hour=6, minute=0, timezone="Asia/Kolkata"),
        id="weekly_shareholding",
        name="Weekly Shareholding Update",
        max_instances=1,
        misfire_grace_time=7200,
    )

    return scheduler


def start_scheduler():
    """Start the global scheduler."""
    scheduler = create_scheduler()
    if scheduler is None:
        return None

    scheduler.start()
    _scheduler_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _scheduler_state["is_running"] = True
    log.info("Scheduler started")
    return scheduler


def get_scheduler_status() -> dict:
    """Return current scheduler status for the admin endpoint."""
    scheduler = None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        # Try to get running jobs info
    except ImportError:
        pass

    next_runs = {}
    try:
        scheduler_obj = create_scheduler()
        if scheduler_obj:
            for job in scheduler_obj.get_jobs():
                next_run = job.next_run_time
                next_runs[job.id] = next_run.isoformat() if next_run else None
    except Exception:
        pass

    return {
        "started_at": _scheduler_state.get("started_at"),
        "is_running": _scheduler_state.get("is_running", False),
        "last_runs": dict(_scheduler_state.get("last_runs", {})),
        "next_runs": next_runs,
        "failure_counts": {
            sym: count
            for sym, count in _scheduler_state.get("failure_counts", {}).items()
            if count > 0
        },
        "skipped_symbols": list(_scheduler_state.get("skipped_symbols", set())),
    }
