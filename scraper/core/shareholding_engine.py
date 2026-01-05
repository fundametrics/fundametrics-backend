"""Fundametrics Shareholding Insights Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class ShareholdingPoint:
    period: str
    timestamp: datetime
    promoter: Optional[float]
    institutional: Optional[float]
    public: Optional[float]


class ShareholdingInsightEngine:
    """Compute Fundametrics-owned signals from normalized shareholding snapshots."""

    _WEIGHTS: Tuple[float, ...] = (0.6, 0.3, 0.1)

    def generate_insights(self, snapshots: Dict[str, Dict[str, Optional[float]]]) -> Dict[str, Any]:
        if not snapshots:
            return self._unavailable_payload()

        series = self._build_series(snapshots)
        if not series:
            return self._unavailable_payload()

        promoter_trend = self._promoter_trend(series)
        institutional_bias = self._institutional_bias(series)
        retail_risk = self._retail_risk(series, promoter_trend, institutional_bias)
        stability = self._ownership_stability(series, promoter_trend, institutional_bias)

        return {
            "promoter_trend": promoter_trend,
            "institutional_bias": institutional_bias,
            "retail_risk": retail_risk,
            "ownership_stability_score": stability,
        }

    # ------------------------------------------------------------------
    def _build_series(self, snapshots: Dict[str, Dict[str, Optional[float]]]) -> List[ShareholdingPoint]:
        points: List[ShareholdingPoint] = []
        for period, data in snapshots.items():
            ts = self._parse_period(period)
            if ts is None:
                continue
            promoter = self._safe_percentage(data.get("promoter"))
            institutional = self._safe_percentage(
                data.get("institutional") or data.get("institutional_investors")
            )
            public = self._safe_percentage(data.get("public"))
            points.append(
                ShareholdingPoint(
                    period=period,
                    timestamp=ts,
                    promoter=promoter,
                    institutional=institutional,
                    public=public,
                )
            )

        points.sort(key=lambda p: p.timestamp)
        return points

    @staticmethod
    def _safe_percentage(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if 0 <= number <= 100 else None

    @staticmethod
    def _parse_period(period: str) -> Optional[datetime]:
        if not period:
            return None
        period = period.strip()
        # YYYY-Qx
        if "-" in period:
            year, rest = period.split("-", 1)
            if len(year) == 4 and year.isdigit() and rest.upper().startswith("Q"):
                quarter = rest[1:]
                if quarter.isdigit():
                    q = int(quarter)
                    if 1 <= q <= 4:
                        month = (q - 1) * 3 + 1
                        return datetime(int(year), month, 1)
        # MMM YYYY
        for fmt in ("%b %Y", "%b-%Y", "%B %Y"):
            try:
                return datetime.strptime(period, fmt)
            except ValueError:
                continue
        # YYYY-MM
        for fmt in ("%Y-%m", "%Y/%m"):
            try:
                return datetime.strptime(period, fmt)
            except ValueError:
                continue
        return None

    # ------------------------------------------------------------------
    def _promoter_trend(self, series: List[ShareholdingPoint]) -> str:
        promoter_values = [p.promoter for p in series if p.promoter is not None]
        promoter_values = promoter_values[-4:]
        if len(promoter_values) < 2:
            return "unknown"

        delta = promoter_values[-1] - promoter_values[0]
        if delta >= 0.5 and self._is_consistent(promoter_values, positive=True):
            return "increasing"
        if delta <= -0.5 and self._is_consistent(promoter_values, positive=False):
            return "decreasing"
        return "flat"

    def _institutional_bias(self, series: List[ShareholdingPoint]) -> str:
        institutional_values = [p.institutional for p in series if p.institutional is not None]
        institutional_values = institutional_values[-4:]
        if len(institutional_values) < 2:
            return "unknown"

        diffs = [institutional_values[i] - institutional_values[i - 1] for i in range(1, len(institutional_values))]
        diffs = diffs[::-1]  # most recent first
        weights = self._WEIGHTS[: len(diffs)]
        weighted = sum(diff * weight for diff, weight in zip(diffs, weights))

        if weighted >= 0.5:
            return "bullish"
        if weighted <= -0.5:
            return "bearish"
        return "neutral"

    def _retail_risk(
        self,
        series: List[ShareholdingPoint],
        promoter_trend: str,
        institutional_bias: str,
    ) -> str:
        public_values = [p.public for p in series if p.public is not None]
        institutional_values = [p.institutional for p in series if p.institutional is not None]
        if len(public_values) < 2:
            return "unknown"

        delta_public = public_values[-1] - public_values[-2]
        delta_institutional = 0.0
        if len(institutional_values) >= 2:
            delta_institutional = institutional_values[-1] - institutional_values[-2]

        if delta_public > 1.5:
            if delta_institutional < -0.5 or promoter_trend == "decreasing":
                return "high"
            if delta_institutional <= 0:
                return "medium"
        if delta_public > 0.5 and delta_institutional <= 0:
            return "medium"
        return "low"

    def _ownership_stability(
        self,
        series: List[ShareholdingPoint],
        promoter_trend: str,
        institutional_bias: str,
    ) -> Optional[int]:
        promoter_values = [p.promoter for p in series if p.promoter is not None]
        institutional_values = [p.institutional for p in series if p.institutional is not None]

        if len(promoter_values) < 2 and len(institutional_values) < 2:
            return None

        score = 100.0
        promoter_vol = self._average_abs_delta(promoter_values)
        institutional_vol = self._average_abs_delta(institutional_values)

        score -= min(40.0, promoter_vol * 8.0)
        score -= min(30.0, institutional_vol * 6.0)

        if promoter_trend == "decreasing":
            score -= 15.0
        if institutional_bias == "distributing":
            score -= 10.0

        if len(promoter_values) < 2 or len(institutional_values) < 2:
            score = min(score, 65.0)

        return max(0, min(100, round(score)))

    # ------------------------------------------------------------------
    @staticmethod
    def _is_consistent(values: Iterable[float], *, positive: bool) -> bool:
        deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
        if positive:
            return all(delta >= -0.1 for delta in deltas)  # allow small reversals
        return all(delta <= 0.1 for delta in deltas)

    @staticmethod
    def _average_abs_delta(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        deltas = [abs(values[i] - values[i - 1]) for i in range(1, len(values))]
        return sum(deltas) / len(deltas)

    @staticmethod
    def _unavailable_payload() -> Dict[str, Any]:
        return {
            "promoter_trend": "unknown",
            "institutional_bias": "unknown",
            "retail_risk": "unknown",
            "ownership_stability_score": None,
        }
