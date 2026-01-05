"""Priority scoring engine for symbol registry records."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

from models.symbol import SymbolRecord

_HIGH_MARKET_CAP = 50_000  # INR Crores
_MID_MARKET_CAP = 10_000
_LOW_MARKET_CAP = 2_000
_STALE_REFRESH_DAYS = 7


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def compute_priority(record: SymbolRecord, context: Dict[str, Any] | None = None) -> int:
    """Return a priority score between 1 and 5 for the given symbol record."""

    context = context or {}
    score = 1

    market_cap = record.market_cap
    if isinstance(market_cap, (int, float)):
        if market_cap >= _HIGH_MARKET_CAP:
            score = 5
        elif market_cap >= _MID_MARKET_CAP:
            score = max(score, 4)
        elif market_cap >= _LOW_MARKET_CAP:
            score = max(score, 3)
        else:
            score = max(score, 2)

    indices: Iterable[str] = context.get("indices") or record.metadata.get("indices", [])
    if indices:
        score = min(score + 1, 5)

    if record.metadata.get("watchlist"):
        score = min(score + 1, 5)

    last_refreshed = _parse_iso8601(record.last_refreshed)
    if not last_refreshed:
        score = min(score + 1, 5)
    else:
        if datetime.now(timezone.utc) - last_refreshed > timedelta(days=_STALE_REFRESH_DAYS):
            score = min(score + 1, 5)

    if record.status != "active":
        score = min(score, 2)

    return max(1, min(score, 5))


__all__ = ["compute_priority"]
