import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scraper.core.signals.base import FundametricsSignal, normalize_severity
from scraper.core.signals.delta import RunDeltaEngine, RunRecord
from scraper.core.signals.fundamental import MetricSnapshot
from scraper.core.signals.ownership import OwnershipSnapshot


def make_run(
    *,
    run_id: str,
    timestamp: datetime,
    revenue: float,
    operating_profit: float,
    net_income: float,
    promoter: float,
    institutional: float,
    retail: float,
    stability_score: float,
) -> dict:
    period_label = "2023-Q4"
    return {
        "symbol": "TEST",
        "run_id": run_id,
        "run_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
        "data": {
            "financials": {
                "income_statement": {
                    "2023-Q3": {
                        "revenue": revenue * 0.9,
                        "operating_profit": operating_profit * 0.9,
                        "net_income": net_income * 0.8,
                    },
                    period_label: {
                        "revenue": revenue,
                        "operating_profit": operating_profit,
                        "net_income": net_income,
                    },
                }
            }
        },
        "shareholding": {
            "summary": {
                "period": period_label,
                "data": {
                    "promoter": promoter,
                    "institutional": institutional,
                    "public": retail,
                },
            },
            "insights": {
                "ownership_stability_score": stability_score,
            },
        },
    }


@pytest.fixture
def delta_engine() -> RunDeltaEngine:
    return RunDeltaEngine()


@pytest.fixture
def mock_runs() -> list[dict]:
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    runs = []
    financials = [
        ("r1", base_time, 100.0, 20.0, 8.0, 60.0, 20.0, 20.0, 90.0),
        ("r2", base_time + timedelta(days=90), 120.0, 28.0, 12.0, 58.0, 22.0, 20.0, 80.0),
        ("r3", base_time + timedelta(days=180), 140.0, 40.0, 6.0, 55.0, 24.0, 21.5, 65.0),
        ("r4", base_time + timedelta(days=270), 150.0, 48.0, 18.0, 50.0, 27.0, 24.5, 42.0),
    ]
    for args in financials:
        runs.append(make_run(
            run_id=args[0],
            timestamp=args[1],
            revenue=args[2],
            operating_profit=args[3],
            net_income=args[4],
            promoter=args[5],
            institutional=args[6],
            retail=args[7],
            stability_score=args[8],
        ))
    return runs


def test_prepare_runs_returns_sorted_records(delta_engine: RunDeltaEngine, mock_runs: list[dict]) -> None:
    records = delta_engine._prepare_runs(mock_runs, lookback=3)
    assert len(records) == 3
    assert all(isinstance(record, RunRecord) for record in records)
    # ensure we kept the most recent entries
    assert [record.run_id for record in records] == ["r2", "r3", "r4"]
    assert records[-1].run_timestamp > records[0].run_timestamp


def test_build_fundamental_snapshots(delta_engine: RunDeltaEngine, mock_runs: list[dict]) -> None:
    records = delta_engine._prepare_runs(mock_runs, lookback=4)
    snapshots = delta_engine._build_fundamental_snapshots(records)
    assert len(snapshots) == 4
    assert all(isinstance(snapshot, MetricSnapshot) for snapshot in snapshots)
    assert snapshots[-1].revenue == pytest.approx(150.0)


def test_build_ownership_snapshots(delta_engine: RunDeltaEngine, mock_runs: list[dict]) -> None:
    records = delta_engine._prepare_runs(mock_runs, lookback=4)
    snapshots = delta_engine._build_ownership_snapshots(records)
    assert len(snapshots) == 4
    assert all(isinstance(snapshot, OwnershipSnapshot) for snapshot in snapshots)
    assert snapshots[-1].promoter == pytest.approx(50.0)
    assert snapshots[-1].stability_score == pytest.approx(42.0)


def test_merge_signals_resolves_conflicts(delta_engine: RunDeltaEngine) -> None:
    now = datetime.now(timezone.utc)
    first = FundametricsSignal(
        signal="margin_expansion",
        severity="medium",
        confidence=0.6,
        explanation="Margins improved",
        timestamp=now - timedelta(days=1),
        metadata={"first": True},
    )
    second = FundametricsSignal(
        signal="margin_expansion",
        severity="high",
        confidence=0.9,
        explanation="Latest run shows strong improvement",
        timestamp=now,
        metadata={"second": True},
    )

    merged = delta_engine._merge_signals([first, second])
    assert len(merged) == 1
    merged_signal = merged[0]
    assert merged_signal.signal == "margin_expansion"
    assert merged_signal.severity in {"low", "medium", "high"}
    assert merged_signal.confidence == pytest.approx(0.75, rel=1e-2)
    assert merged_signal.timestamp == now
    assert merged_signal.explanation == "Margins improved | Latest run shows strong improvement"
    assert merged_signal.metadata == {"first": True, "second": True}


def test_compute_without_runs_returns_empty(delta_engine: RunDeltaEngine) -> None:
    assert delta_engine.compute([]) == []


def test_compute_generates_fundametrics_signals(delta_engine: RunDeltaEngine, mock_runs: list[dict]) -> None:
    signals = delta_engine.compute(mock_runs)
    assert signals, "Expected at least one signal from combined engines"
    for signal in signals:
        assert isinstance(signal, FundametricsSignal)
        assert signal.severity in {"low", "medium", "high"}
        assert 0.0 <= signal.confidence <= 1.0
        assert signal.timestamp.tzinfo is not None
        payload = signal.as_dict()
        assert payload["severity"] in {"low", "medium", "high"}
        assert "source" not in payload
        assert "url" not in payload
