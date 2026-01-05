"""Phase 16E regression tests ensuring integrity guards stay enforced."""

from scraper.core.api_response_builder import FundametricsResponseBuilder
from scraper.core.metrics import MetricValue


def _builder() -> FundametricsResponseBuilder:
    return FundametricsResponseBuilder(
        symbol="BHEL",
        company_name="Bharat Heavy Electricals Limited",
        sector="Capital Goods",
    )


def _metric(value: float, statement_id: str, unit: str = "INR") -> MetricValue:
    return MetricValue(
        value=value,
        unit=unit,
        statement_id=statement_id,
        computed=False,
    )


def test_mixed_statement_operating_margin_rejected():
    builder = _builder()
    consolidated_id = "CONSOLIDATED_NSE_ANNUAL_2024-03-31"
    standalone_id = "STANDALONE_NSE_ANNUAL_2024-03-31"

    builder.set_canonical_financials(
        {
            "income_statement": {
                "Mar 2024": {
                    "revenue": _metric(120.0, consolidated_id),
                    "operating_profit": _metric(24.0, standalone_id),
                    "net_income": _metric(18.0, consolidated_id),
                }
            },
            "balance_sheet": {},
        }
    )

    response = builder.build()
    op_margin = response["metrics"]["values"]["fundametrics_operating_margin"]
    assert op_margin["value"] is None
    assert op_margin["reason"] == "Cross-statement mismatch"
    assert response["metrics"]["integrity"] == "partial"


def test_roe_requires_equity_history():
    builder = _builder()
    statement_id = "CONSOLIDATED_NSE_ANNUAL_2024-03-31"

    builder.set_canonical_financials(
        {
            "income_statement": {
                "Mar 2024": {
                    "revenue": _metric(200.0, statement_id),
                    "operating_profit": _metric(34.0, statement_id),
                    "net_income": _metric(18.0, statement_id),
                }
            },
            "balance_sheet": {
                "Mar 2024": {
                    "shareholder_equity": _metric(210.0, statement_id),
                }
            },
        }
    )

    response = builder.build()
    roe = response["metrics"]["values"]["fundametrics_return_on_equity"]
    assert roe["value"] is None
    assert roe["reason"] == "Insufficient equity history"
    assert response["metrics"]["integrity"] == "partial"


def test_shareholding_delta_incompatible_snapshots():
    builder = _builder()
    builder.set_canonical_financials({"meta": {"exchange": "NSE"}})
    builder.add_shareholding(
        {
            "2024-Q1": {
                "Promoter": 60.0,
                "Institutional Investors": 25.0,
                "Public Shareholding": 15.0,
            },
            "2024-Q2": {
                "Promoter": 62.0,
                "Institutional Investors": 24.0,
                "Others": 14.0,
            },
        }
    )

    response = builder.build()
    shareholding = response["shareholding"]
    assert shareholding["status"] == "available"
    delta = shareholding["delta"]
    assert delta["values"] is None
    assert delta["reason"] == "Incompatible shareholding snapshots"
    assert delta["confidence"] is None


def test_api_metrics_emit_objects_not_floats():
    builder = _builder()
    statement_id = "CONSOLIDATED_NSE_ANNUAL_2024-03-31"
    prior_statement_id = "CONSOLIDATED_NSE_ANNUAL_2023-03-31"

    builder.set_canonical_financials(
        {
            "income_statement": {
                "Mar 2023": {
                    "revenue": _metric(180.0, prior_statement_id),
                    "operating_profit": _metric(28.0, prior_statement_id),
                    "net_income": _metric(16.0, prior_statement_id),
                    "interest": _metric(4.0, prior_statement_id),
                },
                "Mar 2024": {
                    "revenue": _metric(220.0, statement_id),
                    "operating_profit": _metric(40.0, statement_id),
                    "net_income": _metric(22.0, statement_id),
                    "interest": _metric(5.0, statement_id),
                },
            },
            "balance_sheet": {
                "Mar 2023": {
                    "total_assets": _metric(150.0, prior_statement_id),
                    "shareholder_equity": _metric(90.0, prior_statement_id),
                },
                "Mar 2024": {
                    "total_assets": _metric(160.0, statement_id),
                    "shareholder_equity": _metric(96.0, statement_id),
                },
            },
            "meta": {"exchange": "NSE"},
        }
    )

    builder.set_company_metadata(
        {
            "shares_outstanding": 10_000_000,
            "share_price": 125.0,
        }
    )

    response = builder.build()

    for payload in response["financials"]["metrics"].values():
        assert isinstance(payload, dict)
        assert not isinstance(payload, (int, float))

    for payload in response["metrics"]["values"].values():
        assert isinstance(payload, dict)
        assert not isinstance(payload, (int, float))

    for payload in response["financials"]["ratios"].values():
        assert isinstance(payload, dict)
        assert not isinstance(payload, (int, float))
