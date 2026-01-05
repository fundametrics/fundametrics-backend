"""Fundametrics fundamental signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from .base import BaseSignalEngine, FundametricsSignal, normalize_severity


@dataclass(frozen=True)
class MetricSnapshot:
    period: str
    revenue: Optional[float]
    operating_profit: Optional[float]
    net_income: Optional[float]


class FundamentalSignalEngine(BaseSignalEngine):
    ENGINE_NAME = "fundamental"

    def compute(self, snapshots: Iterable[MetricSnapshot]) -> List[FundametricsSignal]:
        snapshots = list(snapshots)
        signals: List[FundametricsSignal] = []

        if len(snapshots) < 3:
            return signals

        margin_signal = self._margin_trend(snapshots)
        if margin_signal:
            signals.append(margin_signal)

        volatility_signal = self._earnings_volatility(snapshots)
        if volatility_signal:
            signals.append(volatility_signal)

        return signals

    def _margin_trend(self, snapshots: List[MetricSnapshot]) -> Optional[FundametricsSignal]:
        latest = snapshots[-1]
        previous = snapshots[-3:-1]

        if latest.revenue in (None, 0) or latest.operating_profit is None:
            return None

        latest_margin = latest.operating_profit / latest.revenue
        previous_margins = [s.operating_profit / s.revenue for s in previous if s.revenue not in (None, 0) and s.operating_profit is not None]

        if len(previous_margins) < 2:
            return None

        avg_previous = sum(previous_margins) / len(previous_margins)
        delta = latest_margin - avg_previous

        if abs(delta) < 0.02:
            return None

        trend = "expansion" if delta > 0 else "compression"
        signal_name = f"margin_{trend}"

        confidence = min(1.0, abs(delta) * 12)
        severity = normalize_severity(confidence)

        explanation = (
            f"Operating margin moved from {avg_previous:.1%} to {latest_margin:.1%}."
        )

        return FundametricsSignal(
            signal=signal_name,
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={
                "latest_period": latest.period,
                "average_previous": avg_previous,
                "latest_margin": latest_margin,
            },
        )

    def _earnings_volatility(self, snapshots: List[MetricSnapshot]) -> Optional[FundametricsSignal]:
        net_incomes = [s.net_income for s in snapshots[-4:] if s.net_income is not None]
        if len(net_incomes) < 4:
            return None

        shifts = [abs(net_incomes[i] - net_incomes[i - 1]) for i in range(1, len(net_incomes))]
        avg_shift = sum(shifts) / len(shifts)

        base = sum(abs(v) for v in net_incomes) / len(net_incomes)
        if base == 0:
            return None

        volatility_ratio = avg_shift / base
        if volatility_ratio < 0.2:
            return None

        confidence = min(1.0, volatility_ratio)
        severity = normalize_severity(confidence)
        explanation = "Net income volatility elevated relative to recent averages."

        return FundametricsSignal(
            signal="earnings_volatility",
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={"volatility_ratio": volatility_ratio},
        )
