"""Utilities for computing data staleness based on TTL metadata."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def extract_ttl(meta_source: Dict[str, Any]) -> Tuple[Optional[datetime], int]:
    """Return the generated timestamp and TTL hours from a metadata dict."""

    generated_raw = (
        meta_source.get("generated")
        or meta_source.get("generated_at")
        or meta_source.get("as_of")
        or meta_source.get("run_timestamp")
    )

    ttl_hours = meta_source.get("ttl_hours") or meta_source.get("ttlHours")

    generated_at = _parse_iso8601(generated_raw if isinstance(generated_raw, str) else None)

    try:
        ttl_value = int(ttl_hours)
    except (TypeError, ValueError):
        ttl_value = 24

    return generated_at, ttl_value


def compute_staleness(latest_payload: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Analyse symbol payload and determine staleness state."""

    now = now or datetime.now(timezone.utc)

    meta = latest_payload.get("meta") or {}
    fallback_meta = latest_payload.get("fundametrics_response", {}).get("metadata", {})
    generated_at, ttl_hours = extract_ttl({**fallback_meta, **meta})

    expires_at: Optional[datetime] = None
    if generated_at is not None:
        expires_at = generated_at + timedelta(hours=max(ttl_hours, 0))

    is_stale = False
    if generated_at is None:
        is_stale = True
    elif expires_at is not None and now >= expires_at:
        is_stale = True

    return {
        "generated_at": generated_at,
        "ttl_hours": ttl_hours,
        "expires_at": expires_at,
        "is_stale": is_stale,
    }


__all__ = ["compute_staleness"]
