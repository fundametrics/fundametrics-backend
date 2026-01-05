"""Health aggregation utilities for the Fundametrics ingestion pipeline."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from scraper.api.settings import ApiSettings

from .repository import DataRepository
from .staleness import compute_staleness
from .state import load_last_ingestion


@dataclass
class HealthReport:
    """Structured bundle of health information."""

    public: Dict[str, Any]
    internal: Dict[str, Any]


_WARNING_LEVELS = ("info", "warning", "critical")


def _normalise_level(level: Optional[str]) -> str:
    if not level:
        return "info"
    level = level.lower()
    if level in _WARNING_LEVELS:
        return level
    if level in {"warn", "warnin", "warns"}:
        return "warning"
    if level in {"crit", "critical"}:
        return "critical"
    return "info"


def _collect_warnings(latest_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []

    root_warn = latest_payload.get("warnings") or []
    if isinstance(root_warn, list):
        warnings.extend(item for item in root_warn if isinstance(item, dict))

    metadata = latest_payload.get("fundametrics_response", {}).get("metadata", {})
    meta_warn = metadata.get("warnings") or []
    if isinstance(meta_warn, list):
        warnings.extend(item for item in meta_warn if isinstance(item, dict))

    return warnings


def _prepare_symbol_sets(settings: ApiSettings, processed: Iterable[str]) -> Tuple[List[str], List[str]]:
    allowlist = set(settings.ingest_allowlist)
    processed_set = {symbol.upper() for symbol in processed}

    if allowlist:
        tracked = sorted({symbol.upper() for symbol in allowlist} | processed_set)
    else:
        tracked = sorted(processed_set)

    never = sorted(symbol for symbol in allowlist if symbol not in processed_set) if allowlist else []
    return tracked, never


def build_health_snapshot(
    settings: ApiSettings,
    repo: Optional[DataRepository] = None,
    *,
    now: Optional[datetime] = None,
) -> HealthReport:
    """Compile an API-ready health summary along with internal diagnostics."""

    repo = repo or DataRepository()
    now = now or datetime.now(timezone.utc)

    processed_symbols = repo.list_symbols()
    tracked_symbols, never_ingested = _prepare_symbol_sets(settings, processed_symbols)

    stale_symbols: List[str] = []
    symbol_details: Dict[str, Any] = {}
    warnings_counter: Counter[str] = Counter()
    warnings_total = 0
    fresh_count = 0
    processed_count = 0

    for symbol in tracked_symbols:
        latest = repo.get_latest(symbol)
        if not latest:
            symbol_details[symbol] = {
                "status": "never_ingested",
            }
            continue

        processed_count += 1
        staleness = compute_staleness(latest, now=now)
        is_stale = staleness["is_stale"]
        if is_stale:
            stale_symbols.append(symbol)
        else:
            fresh_count += 1

        warnings = _collect_warnings(latest)
        warnings_total += len(warnings)
        severity_counts = Counter(_normalise_level(w.get("level")) for w in warnings)
        warnings_counter.update(severity_counts)

        symbol_details[symbol] = {
            "status": "stale" if is_stale else "fresh",
            "generated_at": staleness["generated_at"].isoformat() if staleness["generated_at"] else None,
            "ttl_hours": staleness["ttl_hours"],
            "expires_at": staleness["expires_at"].isoformat() if staleness["expires_at"] else None,
            "warnings": len(warnings),
            "warning_severity": {level: severity_counts.get(level, 0) for level in _WARNING_LEVELS},
        }

    stale_count = len(stale_symbols)
    never_count = len(never_ingested)
    total_symbols = len(tracked_symbols)
    if processed_count == 0:
        stale_ratio = 0.0
    else:
        stale_ratio = stale_count / processed_count

    warnings_by_severity = {level: warnings_counter.get(level, 0) for level in _WARNING_LEVELS}

    ingestion_state = load_last_ingestion() or {}
    last_status = ingestion_state.get("status") or "unknown"
    last_run_at = ingestion_state.get("finished_at") or ingestion_state.get("started_at")

    overall_status = "healthy"
    if last_status == "failed" or stale_ratio > 0.3 or warnings_by_severity.get("critical", 0) > 0:
        overall_status = "unhealthy"
    elif stale_count > 0 or warnings_total > 0 or last_status == "partial":
        overall_status = "degraded"

    public_payload = {
        "status": overall_status,
        "generated_at": now.isoformat(),
        "symbols": {
            "total": total_symbols,
            "fresh": fresh_count,
            "stale": stale_count,
            "never_ingested": never_count,
        },
        "ingestion": {
            "last_run_at": last_run_at,
            "last_status": last_status,
            "last_run_id": ingestion_state.get("run_id"),
            "symbols_processed": ingestion_state.get("symbols_processed", 0),
            "failures": len(ingestion_state.get("failures", [])),
        },
        "warnings": {
            "total": warnings_total,
            "by_severity": warnings_by_severity,
        },
        "system": {
            "ingest_enabled": settings.ingest_enabled,
            "admin_key_configured": settings.admin_key_configured,
            "rate_limit_seconds": settings.ingest_rate_limit_seconds,
            "max_per_run": settings.ingest_max_per_run,
            "safe_to_run_refresh": settings.safe_to_run_refresh,
        },
    }

    internal_payload = {
        "generated_at": now.isoformat(),
        "stale_symbols": stale_symbols,
        "never_ingested": never_ingested,
        "per_symbol": symbol_details,
        "stale_ratio": stale_ratio,
        "ingestion_state": ingestion_state,
    }

    return HealthReport(public=public_payload, internal=internal_payload)


__all__ = ["build_health_snapshot", "HealthReport"]
