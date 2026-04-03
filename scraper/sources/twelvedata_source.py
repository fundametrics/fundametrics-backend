"""
Twelve Data Fallback Source for Fundametrics
=============================================

Used as a last-resort data source when completeness_score < 0.5 after
Screener + yfinance merge. Free tier: max 800 calls/day.
"""

from __future__ import annotations

import os
import uuid
import math
from datetime import datetime, timezone, date
from typing import Any, Dict, Optional

from scraper.utils.logger import get_logger
from scraper.core.errors import ScrapeError

log = get_logger(__name__)

# Daily call counter (resets at midnight UTC)
_daily_counter: Dict[str, int] = {"count": 0, "date": ""}
_MAX_DAILY_CALLS = 800


def _check_rate_limit() -> bool:
    """Return True if we can make another call today."""
    today = date.today().isoformat()
    if _daily_counter["date"] != today:
        _daily_counter["count"] = 0
        _daily_counter["date"] = today
    return _daily_counter["count"] < _MAX_DAILY_CALLS


def _increment_counter():
    today = date.today().isoformat()
    if _daily_counter["date"] != today:
        _daily_counter["count"] = 0
        _daily_counter["date"] = today
    _daily_counter["count"] += 1


def get_daily_usage() -> Dict[str, Any]:
    """Return current daily API usage stats."""
    return {
        "calls_today": _daily_counter.get("count", 0),
        "max_daily": _MAX_DAILY_CALLS,
        "remaining": max(0, _MAX_DAILY_CALLS - _daily_counter.get("count", 0)),
        "date": _daily_counter.get("date", date.today().isoformat()),
    }


def get_financials(symbol: str) -> dict:
    """
    Fetch income statement and balance sheet from Twelve Data API.

    Requires TWELVEDATA_API_KEY environment variable.

    Args:
        symbol: NSE stock symbol (e.g. 'RELIANCE').

    Returns:
        dict with 'income_statement' and 'balance_sheet' keys.

    Raises:
        ScrapeError on failure or rate limit.
    """
    run_id = str(uuid.uuid4())[:8]
    api_key = os.getenv("TWELVEDATA_API_KEY")

    if not api_key:
        log.warning("TWELVEDATA_API_KEY not set, skipping Twelve Data fetch", symbol=symbol)
        return {"income_statement": {}, "balance_sheet": {}, "source": "twelvedata", "status": "skipped"}

    if not _check_rate_limit():
        log.warning("Twelve Data daily rate limit reached", symbol=symbol, usage=_daily_counter["count"])
        return {"income_statement": {}, "balance_sheet": {}, "source": "twelvedata", "status": "rate_limited"}

    log.info("Twelve Data fetch starting", symbol=symbol, run_id=run_id, phase="twelvedata")

    try:
        import requests

        base_url = "https://api.twelvedata.com"
        td_symbol = f"{symbol}:NSE"

        result = {"income_statement": {}, "balance_sheet": {}, "source": "twelvedata", "status": "ok"}

        # Fetch income statement
        _increment_counter()
        resp = requests.get(
            f"{base_url}/income_statement",
            params={"symbol": td_symbol, "apikey": api_key, "period": "annual"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            statements = data.get("income_statement", [])
            if isinstance(statements, list):
                for stmt in statements:
                    period = stmt.get("fiscal_date", "unknown")
                    result["income_statement"][period] = {
                        k: _safe_float(v) for k, v in stmt.items()
                        if k != "fiscal_date"
                    }

        # Fetch balance sheet
        if _check_rate_limit():
            _increment_counter()
            resp = requests.get(
                f"{base_url}/balance_sheet",
                params={"symbol": td_symbol, "apikey": api_key, "period": "annual"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                statements = data.get("balance_sheet", [])
                if isinstance(statements, list):
                    for stmt in statements:
                        period = stmt.get("fiscal_date", "unknown")
                        result["balance_sheet"][period] = {
                            k: _safe_float(v) for k, v in stmt.items()
                            if k != "fiscal_date"
                        }

        log.info(
            "Twelve Data fetch complete",
            symbol=symbol,
            run_id=run_id,
            income_periods=len(result["income_statement"]),
            balance_periods=len(result["balance_sheet"]),
        )
        return result

    except Exception as exc:
        log.error("Twelve Data fetch failed", symbol=symbol, run_id=run_id, error=str(exc))
        raise ScrapeError(
            f"Twelve Data failed for {symbol}: {exc}",
            source="twelvedata",
            symbol=symbol,
            run_id=run_id,
            phase="twelvedata",
        ) from exc


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
