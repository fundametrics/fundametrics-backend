"""
Sector Comparison Engine for Fundametrics
==========================================

Computes sector-level aggregate statistics and individual stock
percentile rankings within peer groups.
"""

from __future__ import annotations

import statistics
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from scraper.utils.logger import get_logger
from scraper.core.repository import DataRepository

log = get_logger(__name__)

# In-memory cache for sector summaries: {sector_name: {"data": dict, "computed_at": datetime}}
_sector_cache: Dict[str, Dict[str, Any]] = {}
_SECTOR_CACHE_TTL_HOURS = 12

# Some metrics are "lower is better"
_LOWER_IS_BETTER = {"pe_ratio", "debt_to_equity", "pb_ratio"}


def _extract_metric_value(run_data: dict, metric_key: str) -> Optional[float]:
    """Extract a numeric metric value from a run payload, trying multiple paths."""
    # Try fundametrics_response -> financials -> metrics
    response = run_data.get("fundametrics_response", run_data)

    # Path 1: financials.metrics.fundametrics_{key}
    metrics = response.get("financials", {}).get("metrics", {})
    for prefix in [f"fundametrics_{metric_key}", metric_key]:
        val = metrics.get(prefix)
        if isinstance(val, dict):
            val = val.get("value")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    # Path 2: financials.ratios.{key}
    ratios = response.get("financials", {}).get("ratios", {})
    for key in [metric_key, f"return_on_{metric_key}" if metric_key in ("equity",) else metric_key]:
        val = ratios.get(key)
        if isinstance(val, dict):
            val = val.get("value")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    # Path 3: top-level metrics block
    top_metrics = response.get("metrics", {}).get("values", {})
    for prefix in [f"fundametrics_{metric_key}", metric_key]:
        val = top_metrics.get(prefix)
        if isinstance(val, dict):
            val = val.get("value")
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    return None


def compute_sector_summary(
    symbols: List[str],
    metric_keys: List[str],
    repository: Optional[DataRepository] = None,
) -> dict:
    """
    Compute aggregate statistics for a list of peer symbols.

    Args:
        symbols: List of NSE symbols in the sector.
        metric_keys: List of metric keys to aggregate (e.g. ['pe_ratio', 'roe', 'roce']).
        repository: DataRepository to load cached runs from.

    Returns:
        {
            "sector_stats": {
                "pe_ratio": {"median": ..., "mean": ..., "p25": ..., "p75": ..., "best_symbol": ..., "worst_symbol": ...},
                ...
            },
            "symbol_data": {symbol: {metric: value, ...}, ...},
            "symbols_count": int,
            "computed_at": str
        }
    """
    repo = repository or DataRepository()

    # Load latest run for each symbol
    symbol_metrics: Dict[str, Dict[str, Optional[float]]] = {}
    for sym in symbols:
        run = repo.get_latest(sym)
        if not run:
            continue
        row: Dict[str, Optional[float]] = {}
        for key in metric_keys:
            row[key] = _extract_metric_value(run, key)
        symbol_metrics[sym] = row

    # Compute aggregates per metric
    sector_stats: Dict[str, Dict[str, Any]] = {}
    for key in metric_keys:
        values_with_symbols: List[Tuple[float, str]] = []
        for sym, metrics in symbol_metrics.items():
            val = metrics.get(key)
            if val is not None:
                values_with_symbols.append((val, sym))

        if not values_with_symbols:
            sector_stats[key] = {
                "median": None, "mean": None, "p25": None, "p75": None,
                "best_symbol": None, "worst_symbol": None, "sample_size": 0,
            }
            continue

        values = [v for v, _ in values_with_symbols]
        values.sort()

        lower_better = key in _LOWER_IS_BETTER
        sorted_pairs = sorted(values_with_symbols, key=lambda x: x[0])

        best = sorted_pairs[0] if lower_better else sorted_pairs[-1]
        worst = sorted_pairs[-1] if lower_better else sorted_pairs[0]

        n = len(values)
        p25_idx = max(0, int(n * 0.25) - 1)
        p75_idx = min(n - 1, int(n * 0.75))

        sector_stats[key] = {
            "median": round(statistics.median(values), 2),
            "mean": round(statistics.mean(values), 2),
            "p25": round(values[p25_idx], 2),
            "p75": round(values[p75_idx], 2),
            "best_symbol": best[1],
            "best_value": round(best[0], 2),
            "worst_symbol": worst[1],
            "worst_value": round(worst[0], 2),
            "sample_size": n,
        }

    return {
        "sector_stats": sector_stats,
        "symbol_data": symbol_metrics,
        "symbols_count": len(symbol_metrics),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_peer_comparison(
    subject_symbol: str,
    peer_symbols: List[str],
    metric_keys: List[str],
    repository: Optional[DataRepository] = None,
) -> dict:
    """
    Compare a stock against its peer group, returning percentile rank for each metric.

    Returns:
        {
            "subject": {"symbol": str, "metrics": {...}},
            "peers": [{"symbol": str, "metrics": {...}}, ...],
            "percentile_ranks": {"pe_ratio": float, ...},
            "sector_summary": {...}
        }
    """
    all_symbols = list(set([subject_symbol] + peer_symbols))
    summary = compute_sector_summary(all_symbols, metric_keys, repository)

    subject_data = summary["symbol_data"].get(subject_symbol, {})
    percentile_ranks: Dict[str, Optional[float]] = {}

    for key in metric_keys:
        subject_val = subject_data.get(key)
        if subject_val is None:
            percentile_ranks[key] = None
            continue

        # Collect all values for this metric
        all_values = []
        for sym, metrics in summary["symbol_data"].items():
            val = metrics.get(key)
            if val is not None:
                all_values.append(val)

        if not all_values:
            percentile_ranks[key] = None
            continue

        lower_better = key in _LOWER_IS_BETTER
        if lower_better:
            # For lower-is-better, percentile = % of peers with HIGHER value
            rank = sum(1 for v in all_values if v > subject_val) / len(all_values)
        else:
            # For higher-is-better, percentile = % of peers with LOWER value
            rank = sum(1 for v in all_values if v < subject_val) / len(all_values)

        percentile_ranks[key] = round(rank * 100, 1)

    # Build peer list
    peers = []
    for sym in peer_symbols:
        if sym in summary["symbol_data"]:
            peers.append({"symbol": sym, "metrics": summary["symbol_data"][sym]})

    return {
        "subject": {"symbol": subject_symbol, "metrics": subject_data},
        "peers": peers,
        "percentile_ranks": percentile_ranks,
        "sector_summary": summary["sector_stats"],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def get_cached_sector_summary(
    sector_name: str,
    symbols: List[str],
    metric_keys: List[str],
    repository: Optional[DataRepository] = None,
    force_refresh: bool = False,
) -> dict:
    """Wrapper with 12-hour caching for sector summaries."""
    cache_key = sector_name.lower().strip()

    if not force_refresh and cache_key in _sector_cache:
        cached = _sector_cache[cache_key]
        age = datetime.now(timezone.utc) - cached["computed_at"]
        if age < timedelta(hours=_SECTOR_CACHE_TTL_HOURS):
            return cached["data"]

    result = compute_sector_summary(symbols, metric_keys, repository)
    result["sector_name"] = sector_name

    _sector_cache[cache_key] = {
        "data": result,
        "computed_at": datetime.now(timezone.utc),
    }

    return result
