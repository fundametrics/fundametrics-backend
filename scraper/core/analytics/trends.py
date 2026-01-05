"""
Trend engine for historical analytics over persisted runs.

Computes:
- Revenue CAGR
- Promoter holding trend
- Signal direction change
- Stability over N runs
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from scraper.core.repository import DataRepository
from scraper.core.observability.logger import get_logger

log = get_logger(__name__)


class TrendDirection:
    STABLE = "stable"
    IMPROVING = "improving"
    DECLINING = "declining"
    UNKNOWN = "unknown"


class TrendEngine:
    """Read-only analytics over historical runs."""

    def __init__(self, repository: DataRepository) -> None:
        self.repo = repository

    # ---------- Helpers ----------
    @staticmethod
    def _cagr(start: Optional[float], end: Optional[float], periods: int) -> Optional[float]:
        """Compound Annual Growth Rate; returns None if inputs invalid."""
        if start is None or end is None or start <= 0 or periods <= 0:
            return None
        try:
            return (end / start) ** (1 / periods) - 1
        except Exception:
            return None

    @staticmethod
    def _linear_trend(values: List[Optional[float]]) -> str:
        """Simple slope-based trend classification."""
        clean = [v for v in values if v is not None]
        if len(clean) < 2:
            return TrendDirection.UNKNOWN
        n = len(clean)
        x_avg = (n - 1) / 2
        y_avg = sum(clean) / n
        num = sum((i - x_avg) * (clean[i] - y_avg) for i in range(n))
        den = sum((i - x_avg) ** 2 for i in range(n))
        if den == 0:
            return TrendDirection.STABLE
        slope = num / den
        if abs(slope) < 1e-6:
            return TrendDirection.STABLE
        return TrendDirection.IMPROVING if slope > 0 else TrendDirection.DECLINING

    @staticmethod
    def _direction_change(prev: Optional[str], cur: Optional[str]) -> str:
        """Classify momentum based on direction changes."""
        if prev == cur or prev is None or cur is None:
            return TrendDirection.STABLE
        if cur == TrendDirection.IMPROVING and prev != TrendDirection.IMPROVING:
            return TrendDirection.IMPROVING
        if cur == TrendDirection.DECLINING and prev != TrendDirection.DECLINING:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    # ---------- Core Computations ----------
    def revenue_cagr(self, symbol: str, periods: int = 4) -> Optional[float]:
        """Compute revenue CAGR over the last N runs."""
        runs = self.repo.load_runs(symbol, limit=periods)
        if len(runs) < 2:
            return None
        revenues = []
        for run in runs:
            rev = run.get("metrics", {}).get("revenue")
            if rev is not None:
                revenues.append(rev)
        if len(revenues) < 2:
            return None
        # Use earliest and latest values
        return self._cagr(revenues[0], revenues[-1], len(revenues) - 1)

    def promoter_trend(self, symbol: str, periods: int = 4) -> str:
        """Classify promoter holding trend over recent runs."""
        runs = self.repo.load_runs(symbol, limit=periods)
        promoter_vals = []
        for run in runs:
            sh = run.get("shareholding", {})
            # Prefer summary data if available
            summary = sh.get("summary", {})
            if isinstance(summary, dict):
                pct = summary.get("data", {}).get("promoter_pct")
            else:
                pct = None
            if pct is None:
                # Fallback to raw shareholding if present (unlikely after sanitization)
                raw = run.get("data", {}).get("shareholding", {})
                pct = raw.get("promoter") if isinstance(raw, dict) else None
            if isinstance(pct, (int, float)):
                promoter_vals.append(float(pct))
        return self._linear_trend(promoter_vals)

    def signal_momentum(self, symbol: str, periods: int = 4) -> str:
        """Aggregate signal direction changes over recent runs."""
        runs = self.repo.load_runs(symbol, limit=periods)
        # Map signal name to latest severity direction
        # We'll use severity order: low < medium < high
        severity_rank = {"low": 1, "medium": 2, "high": 3}
        signal_trends: Dict[str, List[int]] = {}
        for run in runs:
            signals_block = run.get("signals", {}).get("active", [])
            for sig in signals_block:
                name = sig.get("signal")
                sev = sig.get("severity")
                if name and sev in severity_rank:
                    signal_trends.setdefault(name, []).append(severity_rank[sev])
        # For each signal, compute trend and then aggregate momentum
        directions = []
        for vals in signal_trends.values():
            if len(vals) >= 2:
                # Simple check: if latest > previous, improving
                if vals[-1] > vals[-2]:
                    directions.append(TrendDirection.IMPROVING)
                elif vals[-1] < vals[-2]:
                    directions.append(TrendDirection.DECLINING)
                else:
                    directions.append(TrendDirection.STABLE)
        if not directions:
            return TrendDirection.UNKNOWN
        # Majority vote
        improving = directions.count(TrendDirection.IMPROVING)
        declining = directions.count(TrendDirection.DECLINING)
        stable = directions.count(TrendDirection.STABLE)
        if improving > declining and improving > stable:
            return TrendDirection.IMPROVING
        if declining > improving and declining > stable:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    def stability_score(self, symbol: str, periods: int = 4) -> float:
        """Quantify stability across metrics and ownership (0–1, higher = more stable)."""
        runs = self.repo.load_runs(symbol, limit=periods)
        if len(runs) < 2:
            return 0.0
        # Collect series for revenue, promoter, institutional
        revenue_series = []
        promoter_series = []
        institutional_series = []
        for run in runs:
            # Revenue
            rev = run.get("metrics", {}).get("revenue")
            if rev is not None:
                revenue_series.append(float(rev))
            # Promoter
            sh = run.get("shareholding", {})
            summary = sh.get("summary", {})
            if isinstance(summary, dict):
                pct = summary.get("data", {}).get("promoter_pct")
                if isinstance(pct, (int, float)):
                    promoter_series.append(float(pct))
                inst = summary.get("data", {}).get("institutional_pct")
                if isinstance(inst, (int, float)):
                    institutional_series.append(float(inst))
        # Compute coefficient of variation for each series (lower = more stable)
        def cv(series: List[float]) -> float:
            if len(series) < 2:
                return 0.0
            mean = sum(series) / len(series)
            if mean == 0:
                return 0.0
            var = sum((x - mean) ** 2 for x in series) / len(series)
            std = math.sqrt(var)
            return std / mean

        cvs = [cv(revenue_series), cv(promoter_series), cv(institutional_series)]
        # Normalize to stability: 1 - min(1, avg_cv)
        avg_cv = sum(cvs) / len(cvs)
        stability = max(0.0, 1.0 - min(1.0, avg_cv))
        return round(stability, 3)

    # ---------- Public API ----------
    def compute(self, symbol: str, periods: int = 4) -> Dict[str, Any]:
        """Return a consolidated trend summary for a symbol."""
        try:
            revenue_cagr_val = self.revenue_cagr(symbol, periods)
            revenue_trend_str = (
                TrendDirection.IMPROVING
                if (revenue_cagr_val or 0) > 0.02
                else TrendDirection.DECLINING
                if (revenue_cagr_val or 0) < -0.02
                else TrendDirection.STABLE
            )
            return {
                "symbol": symbol,
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "periods_analyzed": periods,
                "revenue": {
                    "cagr": revenue_cagr_val,
                    "trend": revenue_trend_str,
                },
                "promoter": {
                    "trend": self.promoter_trend(symbol, periods),
                },
                "signal_momentum": self.signal_momentum(symbol, periods),
                "stability_score": self.stability_score(symbol, periods),
            }
        except Exception as exc:
            log.error(f"trend_compute_failed for symbol {symbol}: {exc}")
            return {
                "symbol": symbol,
                "computed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
