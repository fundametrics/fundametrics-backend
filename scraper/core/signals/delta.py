"""Run-level delta engine for Fundametrics signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Sequence

from .base import BaseSignalEngine, FundametricsSignal, normalize_severity
from .fundamental import FundamentalSignalEngine, MetricSnapshot
from .ownership import OwnershipSignalEngine, OwnershipSnapshot


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class RunRecord:
    """Minimal view of a persisted Fundametrics run used by the delta engine."""

    symbol: str
    run_id: str
    run_timestamp: datetime
    payload: Dict[str, Any]


class RunDeltaEngine(BaseSignalEngine):
    """Merge signals produced by multiple engines across historical runs."""

    ENGINE_NAME = "run_delta"

    def __init__(
        self,
        *,
        fundamental_engine: FundamentalSignalEngine | None = None,
        ownership_engine: OwnershipSignalEngine | None = None,
    ) -> None:
        self._fundamental = fundamental_engine or FundamentalSignalEngine()
        self._ownership = ownership_engine or OwnershipSignalEngine()

    # ------------------------------------------------------------------
    def compute(self, runs: Sequence[Dict[str, Any]], lookback: int = 4) -> List[FundametricsSignal]:
        """Compute unified signals from the most recent `lookback` runs."""

        run_records = self._prepare_runs(runs, lookback)
        if not run_records:
            return []

        fundamental_snapshots = self._build_fundamental_snapshots(run_records)
        ownership_snapshots = self._build_ownership_snapshots(run_records)

        signals: List[FundametricsSignal] = []
        signals.extend(self._fundamental.compute(fundamental_snapshots))
        signals.extend(self._ownership.compute(ownership_snapshots))

        return self._merge_signals(signals)

    # ------------------------------------------------------------------
    def _prepare_runs(self, runs: Sequence[Dict[str, Any]], lookback: int) -> List[RunRecord]:
        records: List[RunRecord] = []
        for run in runs:
            try:
                run_id = run["run_id"]
                timestamp_raw = run["run_timestamp"]
                payload = run
            except KeyError:
                continue

            records.append(
                RunRecord(
                    symbol=run.get("symbol", "UNKNOWN"),
                    run_id=run_id,
                    run_timestamp=_parse_timestamp(timestamp_raw),
                    payload=payload,
                )
            )

        records.sort(key=lambda r: r.run_timestamp)
        if lookback > 0:
            records = records[-lookback:]
        return records

    # Fundamental -------------------------------------------------------
    def _build_fundamental_snapshots(self, runs: List[RunRecord]) -> List[MetricSnapshot]:
        snapshots: List[MetricSnapshot] = []
        for run in runs:
            data = run.payload.get("data", {})
            financials = data.get("financials", {})
            income_stmt = financials.get("income_statement")
            if not isinstance(income_stmt, dict):
                continue

            periods = sorted(income_stmt.keys())
            if not periods:
                continue

            latest_period = periods[-1]
            latest_row = income_stmt.get(latest_period, {})

            snapshots.append(
                MetricSnapshot(
                    period=f"{run.run_timestamp.date()}-{latest_period}",
                    revenue=_coerce_number(latest_row.get("revenue")),
                    operating_profit=_coerce_number(latest_row.get("operating_profit")),
                    net_income=_coerce_number(latest_row.get("net_income")),
                )
            )
        return snapshots

    # Ownership ---------------------------------------------------------
    def _build_ownership_snapshots(self, runs: List[RunRecord]) -> List[OwnershipSnapshot]:
        snapshots: List[OwnershipSnapshot] = []
        for run in runs:
            shareholding = run.payload.get("shareholding") or {}
            summary = shareholding.get("summary") or {}
            summary_data = summary.get("data") or {}

            snapshots.append(
                OwnershipSnapshot(
                    period=summary.get("period") or run.run_timestamp.isoformat(),
                    promoter=_coerce_number(summary_data.get("promoter")),
                    institutional=_coerce_number(summary_data.get("institutional")),
                    retail=_coerce_number(summary_data.get("public")),
                    stability_score=_coerce_number(
                        run.payload.get("shareholding", {})
                        .get("insights", {})
                        .get("ownership_stability_score")
                    ),
                )
            )
        return snapshots

    # Merge -------------------------------------------------------------
    def _merge_signals(self, signals: List[FundametricsSignal]) -> List[FundametricsSignal]:
        merged: Dict[str, FundametricsSignal] = {}
        for signal in signals:
            existing = merged.get(signal.signal)
            if existing is None:
                merged[signal.signal] = signal
                continue

            confidence = self.clamp_confidence((existing.confidence + signal.confidence) / 2)
            severity = normalize_severity(confidence)
            timestamp = max(existing.timestamp, signal.timestamp)

            explanation = f"{existing.explanation} | {signal.explanation}"
            metadata = {**(existing.metadata or {}), **(signal.metadata or {})}

            merged[signal.signal] = FundametricsSignal(
                signal=signal.signal,
                severity=severity,
                confidence=confidence,
                explanation=explanation,
                timestamp=timestamp,
                metadata=metadata,
            )
        return list(merged.values())


def _coerce_number(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
