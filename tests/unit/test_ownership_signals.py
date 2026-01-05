import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scraper.core.signals.base import normalize_severity
from scraper.core.signals.ownership import OwnershipSignalEngine, OwnershipSnapshot


def make_snapshot(period: str, promoter: float, institutional: float, retail: float, stability: float | None = None) -> OwnershipSnapshot:
    return OwnershipSnapshot(
        period=period,
        promoter=promoter,
        institutional=institutional,
        retail=retail,
        stability_score=stability,
    )


@pytest.fixture
def engine() -> OwnershipSignalEngine:
    return OwnershipSignalEngine()


def test_promoter_exit_warning(engine: OwnershipSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 55.0, 30.0, 15.0),
        make_snapshot("2023-Q2", 54.0, 31.0, 15.0),
        make_snapshot("2023-Q3", 49.0, 32.0, 19.0),
        make_snapshot("2023-Q4", 48.0, 33.0, 19.0),
    ]

    signal = engine._promoter_exit_warning(snapshots)
    assert signal is not None
    assert signal.signal == "promoter_exit_warning"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["delta"] < 0


def test_institutional_accumulation(engine: OwnershipSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 55.0, 30.0, 15.0),
        make_snapshot("2023-Q2", 55.2, 31.0, 13.8),
        make_snapshot("2023-Q3", 55.5, 33.0, 11.5),
        make_snapshot("2023-Q4", 55.4, 35.5, 9.1),
    ]

    signal = engine._institutional_accumulation(snapshots)
    assert signal is not None
    assert signal.signal == "institutional_accumulation"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["promoter_stable"]


def test_retail_overcrowding(engine: OwnershipSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q2", 54.0, 33.0, 13.0),
        make_snapshot("2023-Q3", 54.0, 32.2, 13.8),
        make_snapshot("2023-Q4", 54.1, 31.5, 15.3),
    ]

    signal = engine._retail_overcrowding(snapshots)
    assert signal is not None
    assert signal.signal == "retail_overcrowding"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["retail_delta"] > 0


def test_ownership_instability(engine: OwnershipSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q2", 55.0, 30.0, 15.0, 90.0),
        make_snapshot("2023-Q3", 52.5, 28.0, 19.5, 70.0),
        make_snapshot("2023-Q4", 50.0, 27.0, 23.0, 50.0),
        make_snapshot("2024-Q1", 49.0, 26.0, 25.0, 42.0),
    ]

    signal = engine._ownership_instability(snapshots)
    assert signal is not None
    assert signal.signal == "ownership_instability"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["volatility"] > 0


def test_engine_compute_returns_all_signals(engine: OwnershipSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 55.0, 30.0, 15.0, 90.0),
        make_snapshot("2023-Q2", 54.0, 32.0, 14.0, 75.0),
        make_snapshot("2023-Q3", 52.0, 33.5, 14.5, 60.0),
        make_snapshot("2023-Q4", 48.5, 35.5, 16.0, 45.0),
    ]

    signals = engine.compute(snapshots)
    names = {signal.signal for signal in signals}
    assert names == {
        "promoter_exit_warning",
        "institutional_accumulation",
        "ownership_instability",
    }
    for signal in signals:
        assert signal.severity in {"low", "medium", "high"}


def test_normalize_severity_sanity() -> None:
    assert normalize_severity(0.1) == "low"
    assert normalize_severity(0.4) == "medium"
    assert normalize_severity(0.8) == "high"
