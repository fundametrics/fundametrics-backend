"""
NSE India Direct Data Source for Fundametrics
==============================================

Fetches shareholding pattern and corporate actions directly from NSE India's public API.
No API key required, but browser-like headers and session cookie priming are mandatory.
"""

from __future__ import annotations

import time
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path

import requests

from scraper.utils.logger import get_logger
from scraper.core.errors import ScrapeError

log = get_logger(__name__)

# In-memory cache: {symbol: {"data": dict, "fetched_at": datetime}}
_shareholding_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_HOURS = 6  # Shareholding only changes quarterly

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com",
    "Connection": "keep-alive",
}

_NSE_DELAY_SECONDS = 2


def _create_nse_session() -> requests.Session:
    """Create a requests.Session pre-primed with NSE cookies."""
    session = requests.Session()
    session.headers.update(_NSE_HEADERS)

    try:
        # Prime session cookies by visiting the homepage first
        resp = session.get("https://www.nseindia.com", timeout=10)
        resp.raise_for_status()
        log.debug("NSE session primed", cookies=len(session.cookies))
    except Exception as exc:
        log.warning("NSE session priming failed, proceeding anyway", error=str(exc))

    return session


def get_shareholding(symbol: str, force_refresh: bool = False) -> dict:
    """
    Fetch shareholding pattern from NSE India.

    Uses in-memory cache with 6-hour TTL (shareholding changes quarterly).

    Returns:
        dict matching the existing shareholding schema:
        {
            "status": "available",
            "summary": {"promoter": float, "fii": float, "dii": float, "public": float},
            "quarter_date": str,
            "changes": {...},
            "insights": [...]
        }

    Raises:
        ScrapeError on failure.
    """
    run_id = str(uuid.uuid4())[:8]
    log.info("NSE shareholding fetch starting", symbol=symbol, run_id=run_id, phase="nse_shareholding")

    # Check cache
    if not force_refresh and symbol.upper() in _shareholding_cache:
        cached = _shareholding_cache[symbol.upper()]
        age = datetime.now(timezone.utc) - cached["fetched_at"]
        if age < timedelta(hours=_CACHE_TTL_HOURS):
            log.info("NSE shareholding cache hit", symbol=symbol, age_minutes=int(age.total_seconds() / 60))
            return cached["data"]

    try:
        session = _create_nse_session()
        time.sleep(_NSE_DELAY_SECONDS)

        url = f"https://www.nseindia.com/api/corporate-shareholding-pattern?symbol={symbol.upper()}&series=EQ"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        # Parse the response
        data = _parse_shareholding_response(raw, symbol)

        # Cache it
        _shareholding_cache[symbol.upper()] = {
            "data": data,
            "fetched_at": datetime.now(timezone.utc),
        }

        log.info("NSE shareholding fetch complete", symbol=symbol, run_id=run_id, status=data.get("status"))
        return data

    except ScrapeError:
        raise
    except Exception as exc:
        log.error("NSE shareholding fetch failed", symbol=symbol, run_id=run_id, error=str(exc))
        raise ScrapeError(
            f"NSE shareholding failed for {symbol}: {exc}",
            source="nse_india",
            symbol=symbol,
            run_id=run_id,
            phase="nse_shareholding",
        ) from exc


def _parse_shareholding_response(raw: Any, symbol: str) -> dict:
    """Parse NSE shareholding API response into Fundametrics schema."""
    if not raw or not isinstance(raw, (dict, list)):
        return {"status": "unavailable", "summary": {}, "insights": []}

    # NSE returns a list of quarterly data
    records = raw if isinstance(raw, list) else raw.get("data", [])
    if not records:
        return {"status": "unavailable", "summary": {}, "insights": []}

    # Get latest quarter
    latest = records[0] if records else {}
    previous = records[1] if len(records) > 1 else None

    summary = {}
    changes = {}

    # Extract categories - NSE uses nested structure
    def _extract_percentage(record: dict, category_keys: List[str]) -> Optional[float]:
        """Try multiple field paths to find a percentage."""
        for key in category_keys:
            val = record.get(key)
            if val is not None:
                try:
                    return round(float(val), 2)
                except (ValueError, TypeError):
                    continue
        return None

    # Common NSE field mappings
    promoter_pct = _extract_percentage(latest, ["promoterAndPromoterGroup", "promotersPer", "promoters"])
    fii_pct = _extract_percentage(latest, ["foreignInstitutions", "fiiPer", "fii"])
    dii_pct = _extract_percentage(latest, ["mutualFunds", "diiPer", "dii"])
    public_pct = _extract_percentage(latest, ["publicShareholding", "publicPer", "public"])

    if promoter_pct is not None:
        summary["promoter"] = promoter_pct
    if fii_pct is not None:
        summary["fii"] = fii_pct
    if dii_pct is not None:
        summary["dii"] = dii_pct
    if public_pct is not None:
        summary["public"] = public_pct

    # Compute changes from previous quarter
    if previous:
        prev_promoter = _extract_percentage(previous, ["promoterAndPromoterGroup", "promotersPer", "promoters"])
        prev_fii = _extract_percentage(previous, ["foreignInstitutions", "fiiPer", "fii"])
        prev_dii = _extract_percentage(previous, ["mutualFunds", "diiPer", "dii"])
        prev_public = _extract_percentage(previous, ["publicShareholding", "publicPer", "public"])

        if promoter_pct is not None and prev_promoter is not None:
            changes["promoter"] = round(promoter_pct - prev_promoter, 2)
        if fii_pct is not None and prev_fii is not None:
            changes["fii"] = round(fii_pct - prev_fii, 2)
        if dii_pct is not None and prev_dii is not None:
            changes["dii"] = round(dii_pct - prev_dii, 2)
        if public_pct is not None and prev_public is not None:
            changes["public"] = round(public_pct - prev_public, 2)

    quarter_date = latest.get("date") or latest.get("quarter") or None
    insights = _generate_shareholding_insights(summary, changes)

    status = "available" if summary else "unavailable"

    return {
        "status": status,
        "summary": summary,
        "quarter_date": quarter_date,
        "changes": changes,
        "insights": insights,
        "source": "nse_india",
    }


def _generate_shareholding_insights(summary: dict, changes: dict) -> List[dict]:
    """Generate human-readable insights from shareholding data."""
    insights = []

    promoter = summary.get("promoter")
    if promoter is not None:
        if promoter > 70:
            insights.append({
                "title": "High promoter holding",
                "description": f"Promoter stake is {promoter}%, indicating strong promoter confidence.",
            })
        elif promoter < 30:
            insights.append({
                "title": "Low promoter holding",
                "description": f"Promoter stake is only {promoter}%, which may indicate dispersed ownership.",
            })

    promoter_change = changes.get("promoter")
    if promoter_change is not None:
        if promoter_change < -1:
            insights.append({
                "title": "Promoter stake decreased",
                "description": f"Promoter holding decreased by {abs(promoter_change):.2f}% QoQ.",
            })
        elif promoter_change > 1:
            insights.append({
                "title": "Promoter stake increased",
                "description": f"Promoter holding increased by {promoter_change:.2f}% QoQ.",
            })

    fii_change = changes.get("fii")
    if fii_change is not None and abs(fii_change) > 0.5:
        direction = "increased" if fii_change > 0 else "decreased"
        insights.append({
            "title": f"FII {direction}",
            "description": f"Foreign institutional holding {direction} by {abs(fii_change):.2f}% QoQ.",
        })

    return insights


def get_corporate_actions(symbol: str) -> list:
    """
    Fetch corporate actions (dividends, splits, bonuses) from NSE.

    Returns:
        list of corporate action dicts.
    """
    run_id = str(uuid.uuid4())[:8]
    log.info("NSE corporate actions fetch starting", symbol=symbol, run_id=run_id, phase="nse_actions")

    try:
        session = _create_nse_session()
        time.sleep(_NSE_DELAY_SECONDS)

        url = f"https://www.nseindia.com/api/corporates-corporateActions?index=equities&symbol={symbol.upper()}"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        raw = resp.json()

        actions = raw if isinstance(raw, list) else raw.get("data", [])
        log.info("NSE corporate actions fetch complete", symbol=symbol, count=len(actions))
        return actions

    except Exception as exc:
        log.warning("NSE corporate actions fetch failed", symbol=symbol, error=str(exc))
        return []
