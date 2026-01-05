import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scraper.core.signals.base import normalize_severity
from scraper.core.signals.fundamental import FundamentalSignalEngine, MetricSnapshot


def make_snapshot(period: str, revenue: float, operating_profit: float, net_income: float) -> MetricSnapshot:
    return MetricSnapshot(
        period=period,
        revenue=revenue,
        operating_profit=operating_profit,
        net_income=net_income,
    )


@pytest.fixture
def engine() -> FundamentalSignalEngine:
    return FundamentalSignalEngine()


def test_margin_expansion_signal(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 100.0, 20.0, 12.0),
        make_snapshot("2023-Q2", 110.0, 22.0, 14.0),
        make_snapshot("2023-Q3", 120.0, 36.0, 18.0),
    ]

    signal = engine._margin_trend(snapshots)
    assert signal is not None
    assert signal.signal == "margin_expansion"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["latest_period"] == "2023-Q3"


def test_margin_compression_signal(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 120.0, 36.0, 18.0),
        make_snapshot("2023-Q2", 110.0, 22.0, 14.0),
        make_snapshot("2023-Q3", 100.0, 20.0, 12.0),
    ]

    signal = engine._margin_trend(snapshots)
    assert signal is not None
    assert signal.signal == "margin_compression"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["latest_period"] == "2023-Q3"


def test_margin_trend_requires_history(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 100.0, 20.0, 12.0),
        make_snapshot("2023-Q2", 110.0, 22.0, 14.0),
    ]

    assert engine._margin_trend(snapshots) is None


def test_earnings_volatility_signal(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2022-Q4", 100.0, 20.0, 30.0),
        make_snapshot("2023-Q1", 100.0, 20.0, 5.0),
        make_snapshot("2023-Q2", 100.0, 20.0, 25.0),
        make_snapshot("2023-Q3", 100.0, 20.0, 8.0),
    ]

    signal = engine._earnings_volatility(snapshots)
    assert signal is not None
    assert signal.signal == "earnings_volatility"
    assert signal.severity in {"low", "medium", "high"}
    assert signal.metadata["volatility_ratio"] > 0


def test_compute_returns_expected_signals(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2022-Q4", 100.0, 20.0, 30.0),
        make_snapshot("2023-Q1", 110.0, 22.0, 5.0),
        make_snapshot("2023-Q2", 120.0, 36.0, 25.0),
        make_snapshot("2023-Q3", 130.0, 40.0, 8.0),
    ]

    signals = engine.compute(snapshots)
    names = {signal.signal for signal in signals}
    assert names == {"margin_expansion", "earnings_volatility"}
    for signal in signals:
        assert signal.severity in {"low", "medium", "high"}
        assert 0.0 <= signal.confidence <= 1.0


def test_compute_requires_three_snapshots(engine: FundamentalSignalEngine) -> None:
    snapshots = [
        make_snapshot("2023-Q1", 100.0, 20.0, 12.0),
        make_snapshot("2023-Q2", 110.0, 22.0, 14.0),
    ]

    assert engine.compute(snapshots) == []


def test_clamp_confidence_bounds(engine: FundamentalSignalEngine) -> None:
    assert engine.clamp_confidence(-0.3) == 0.0
    assert engine.clamp_confidence(1.3) == 1.0
    assert engine.clamp_confidence(0.55) == 0.55


def test_normalize_severity_helper() -> None:
    assert normalize_severity(0.2) == "low"
    assert normalize_severity(0.4) == "medium"
    assert normalize_severity(0.9) == "high"
