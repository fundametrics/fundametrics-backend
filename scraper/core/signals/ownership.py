"""Ownership-centric Fundametrics signal engine."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, List, Optional

from .base import BaseSignalEngine, FundametricsSignal, normalize_severity


@dataclass(frozen=True)
class OwnershipSnapshot:
    period: str
    promoter: Optional[float]
    institutional: Optional[float]
    retail: Optional[float]
    stability_score: Optional[float] = None


class OwnershipSignalEngine(BaseSignalEngine):
    """Compute Fundametrics ownership signals from historical shareholding snapshots."""

    ENGINE_NAME = "ownership"

    def compute(self, snapshots: Iterable[OwnershipSnapshot]) -> List[FundametricsSignal]:
        snapshots = list(snapshots)
        if len(snapshots) < 3:
            return []

        signals: List[FundametricsSignal] = []

        promoter_signal = self._promoter_exit_warning(snapshots)
        if promoter_signal:
            signals.append(promoter_signal)

        institutional_signal = self._institutional_accumulation(snapshots)
        if institutional_signal:
            signals.append(institutional_signal)

        retail_signal = self._retail_overcrowding(snapshots)
        if retail_signal:
            signals.append(retail_signal)

        instability_signal = self._ownership_instability(snapshots)
        if instability_signal:
            signals.append(instability_signal)

        return signals

    # ------------------------------------------------------------------
    def _promoter_exit_warning(self, snapshots: List[OwnershipSnapshot]) -> Optional[FundametricsSignal]:
        promoter_series = [s.promoter for s in snapshots if s.promoter is not None]
        if len(promoter_series) < 3:
            return None

        latest = promoter_series[-1]
        prev_avg = mean(promoter_series[-3:-1])
        delta = latest - prev_avg

        if delta >= -0.5:
            return None

        slope = promoter_series[-1] - promoter_series[-3]
        magnitude = abs(delta)
        confidence = self.clamp_confidence(magnitude / 5.0)
        severity = normalize_severity(confidence)

        explanation = (
            f"Promoter holding dropped from {prev_avg:.2f}% to {latest:.2f}% over recent periods."
        )

        return FundametricsSignal(
            signal="promoter_exit_warning",
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={
                "delta": delta,
                "slope": slope,
            },
        )

    def _institutional_accumulation(self, snapshots: List[OwnershipSnapshot]) -> Optional[FundametricsSignal]:
        institutional_series = [s.institutional for s in snapshots if s.institutional is not None]
        promoter_series = [s.promoter for s in snapshots if s.promoter is not None]
        if len(institutional_series) < 3:
            return None

        latest = institutional_series[-1]
        prev_avg = mean(institutional_series[-3:-1])
        delta = latest - prev_avg
        if delta <= 0.5:
            return None

        promoter_stable = False
        if len(promoter_series) >= 3:
            promoter_delta = promoter_series[-1] - mean(promoter_series[-3:-1])
            promoter_stable = promoter_delta > -0.25

        confidence = self.clamp_confidence((delta / 5.0) + (0.15 if promoter_stable else 0.0))
        severity = normalize_severity(confidence)

        explanation = "Institutional ownership has risen consistently across recent quarters."

        return FundametricsSignal(
            signal="institutional_accumulation",
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={
                "delta": delta,
                "promoter_stable": promoter_stable,
            },
        )

    def _retail_overcrowding(self, snapshots: List[OwnershipSnapshot]) -> Optional[FundametricsSignal]:
        retail_series = [s.retail for s in snapshots if s.retail is not None]
        institutional_series = [s.institutional for s in snapshots if s.institutional is not None]
        if len(retail_series) < 2 or len(institutional_series) < 2:
            return None

        retail_delta = retail_series[-1] - retail_series[-2]
        institutional_delta = institutional_series[-1] - institutional_series[-2]

        if retail_delta <= 0.5 or institutional_delta >= -0.3:
            return None

        confidence = self.clamp_confidence((retail_delta / 3.0) + (-institutional_delta / 4.0))
        severity = normalize_severity(confidence)

        explanation = "Retail ownership is rising while institutional participation is dropping."

        return FundametricsSignal(
            signal="retail_overcrowding",
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={
                "retail_delta": retail_delta,
                "institutional_delta": institutional_delta,
            },
        )

    def _ownership_instability(self, snapshots: List[OwnershipSnapshot]) -> Optional[FundametricsSignal]:
        stability_values = [s.stability_score for s in snapshots if s.stability_score is not None]
        promoter_series = [s.promoter for s in snapshots if s.promoter is not None]
        institutional_series = [s.institutional for s in snapshots if s.institutional is not None]

        if not stability_values or len(promoter_series) < 3 or len(institutional_series) < 3:
            return None

        latest_stability = stability_values[-1]
        prev_avg = mean(stability_values[:-1]) if len(stability_values) > 1 else latest_stability
        stability_drop = prev_avg - latest_stability

        promoter_vol = pstdev(promoter_series[-3:]) if len(promoter_series) >= 3 else 0.0
        institutional_vol = pstdev(institutional_series[-3:]) if len(institutional_series) >= 3 else 0.0

        volatility = promoter_vol + institutional_vol

        if stability_drop < 5 and volatility < 1.5:
            return None

        confidence = self.clamp_confidence((stability_drop / 20.0) + (volatility / 8.0))
        severity = normalize_severity(confidence)

        explanation = "Ownership mix is unstable; both promoter and institutional holdings are volatile."

        return FundametricsSignal(
            signal="ownership_instability",
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            timestamp=self.now(),
            metadata={
                "stability_drop": stability_drop,
                "volatility": volatility,
            },
        )
