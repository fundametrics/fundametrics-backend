"""Phase 17A confidence regressions and guardrails."""

from datetime import datetime, timedelta, timezone

from scraper.core.api_response_builder import FundametricsResponseBuilder
from scraper.core.confidence import compute_confidence
from scraper.core.metrics import MetricValue
from scraper.core.metrics_engine import FundametricsMetricsEngine
from scraper.core.ratios_engine import FundametricsRatiosEngine


def _statement_id() -> str:
    return "CONSOLIDATED_NSE_ANNUAL_2024-03-31"


def _metric_with_confidence(value: float, context: dict, *, now: datetime) -> MetricValue:
    metric = MetricValue(
        value=value,
        unit="INR",
        statement_id=_statement_id(),
        computed=False,
    )
    metric.confidence_inputs = context
    metric.confidence = compute_confidence(metric, None, now)
    return metric


def test_confidence_downgrades_on_staleness() -> None:
    engine = FundametricsMetricsEngine()
    anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    engine._now = lambda: anchor  # type: ignore[assignment]

    income_statement = {
        "FY2024": {
            "revenue": 100.0,
            "operating_profit": 25.0,
            "net_income": 12.0,
        }
    }

    metadata_fresh = {
        "generated": anchor.isoformat(),
        "ttl_hours": 24,
    }
    fresh_metrics = engine.compute_metric_values(
        income_statement=income_statement,
        balance_sheet={},
        metadata=metadata_fresh,
    )
    fresh_score = fresh_metrics["fundametrics_operating_margin"].confidence.score  # type: ignore[union-attr]
    assert fresh_score >= 60

    metadata_stale = {
        "generated": (anchor - timedelta(days=30)).isoformat(),
        "ttl_hours": 24,
    }
    stale_metrics = engine.compute_metric_values(
        income_statement=income_statement,
        balance_sheet={},
        metadata=metadata_stale,
    )
    stale_score = stale_metrics["fundametrics_operating_margin"].confidence.score  # type: ignore[union-attr]
    assert stale_score < 60

    builder = FundametricsResponseBuilder(symbol="TEST", company_name="Test Corp", sector="Testing")
    fresh_entry = {
        "value": fresh_metrics["fundametrics_operating_margin"].value,
        "confidence": fresh_metrics["fundametrics_operating_margin"].confidence.to_dict(),  # type: ignore[union-attr]
    }
    assert builder._resolve_integrity({"fundametrics_operating_margin": fresh_entry}, {}) == "verified"

    stale_entry = {
        "value": stale_metrics["fundametrics_operating_margin"].value,
        "confidence": stale_metrics["fundametrics_operating_margin"].confidence.to_dict(),  # type: ignore[union-attr]
    }
    assert builder._resolve_integrity({"fundametrics_operating_margin": stale_entry}, {}) == "partial"


def test_ratio_confidence_inherits_weakest_input() -> None:
    engine = FundametricsRatiosEngine()
    anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    engine._now = lambda: anchor  # type: ignore[assignment]

    high_context = {
        "source_type": "exchange",
        "generated_at": anchor.isoformat(),
        "ttl_hours": 24,
        "statement_status": "matched",
        "completeness_ratio": 1.0,
    }
    weak_context = {
        "source_type": "aggregator",
        "generated_at": (anchor - timedelta(days=30)).isoformat(),
        "ttl_hours": 24,
        "statement_status": "matched",
        "completeness_ratio": 0.5,
    }

    numerator = _metric_with_confidence(40.0, high_context, now=anchor)
    denominator = _metric_with_confidence(80.0, weak_context, now=anchor)

    ratio_metric = engine._derive_ratio(numerator, denominator, "%", "Unavailable")
    ratio_metric = engine._seed_confidence(
        ratio_metric,
        inputs=[numerator, denominator],
        metadata={},
    )
    ratio_metric = engine._cap_confidence_downstream(ratio_metric, [numerator, denominator])

    numerator_score = numerator.confidence.score  # type: ignore[union-attr]
    denominator_score = denominator.confidence.score  # type: ignore[union-attr]
    ratio_score = ratio_metric.confidence.score  # type: ignore[union-attr]

    assert ratio_score <= min(numerator_score, denominator_score)


def test_no_confidence_for_null_metrics() -> None:
    builder = FundametricsResponseBuilder(symbol="BHEL", company_name="BHEL", sector="Capital Goods")
    consolidated_id = "CONSOLIDATED_NSE_ANNUAL_2024-03-31"
    standalone_id = "STANDALONE_NSE_ANNUAL_2024-03-31"

    builder.set_canonical_financials(
        {
            "income_statement": {
                "FY2024": {
                    "revenue": MetricValue(value=120.0, unit="INR", statement_id=consolidated_id, computed=False),
                    "operating_profit": MetricValue(value=24.0, unit="INR", statement_id=standalone_id, computed=False),
                }
            }
        }
    )

    response = builder.build()
    payload = response["metrics"]["values"]["fundametrics_operating_margin"]

    assert payload["value"] is None
    assert "confidence" not in payload
