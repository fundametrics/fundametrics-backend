import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from main import run_scraper
from scraper.core.repository import DataRepository


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def mock_scraper_responses():
    """Provide minimal mocked scraper payloads to avoid network calls."""
    return {
        "financial": {
            "metadata": {"company_name": "TestCo", "sector": "Technology"},
            "financials": {
                "income_statement": {
                    "Revenue": [1000, 1100],
                    "Net Profit": [120, 140],
                },
                "balance_sheet": {
                    "Total Assets": [800, 850],
                },
                "cash_flow": {},
                "metrics": {
                    "Operating Margin": [0.12, 0.127],
                    "Net Margin": [0.12, 0.127],
                    "ROCE": [0.15, 0.165],
                },
            },
        },
        "shareholding": {
            "shareholding": {
                "promoter": 55.0,
                "institutional": 30.0,
                "retail": 15.0,
                "period": "2024-Q4",
            }
        },
        "profile": {
            "company_name": "TestCo",
            "sector": "Technology",
            "industry": "Software",
        },
    }


@patch("scraper.sources.screener.ScreenerScraper.scrape_stock")
@patch("scraper.sources.trendlyne.TrendlyneScraper.scrape_stock")
def test_pipeline_signals_persisted_and_readable(
    mock_trendlyne, mock_screener, temp_output_dir, mock_scraper_responses
):
    mock_screener.return_value = mock_scraper_responses["financial"]
    mock_trendlyne.return_value = mock_scraper_responses["profile"]
    run_ids = run_scraper(
        symbol="TEST",
        output_dir=temp_output_dir,
        persist_runs=True,
        signals=True,
        shareholding=True,
        trendlyne=True,
    )
    assert len(run_ids) == 1
    repo = DataRepository(base_dir=temp_output_dir)
    latest = repo.get_latest("TEST")
    assert latest is not None
    # Verify signals block exists in persisted payload
    assert "signals" in latest
    signals_block = latest["signals"]
    assert "active" in signals_block
    assert isinstance(signals_block["active"], list)
    # Should have merged signals from fundamental and ownership engines
    assert len(signals_block["active"]) >= 1
    for sig in signals_block["active"]:
        assert "signal" in sig
        assert "severity" in sig
        assert "confidence" in sig
        assert "explanation" in sig
        assert "generated_at" in sig
        # No internal leakage
        assert "raw_snapshot" not in sig
        assert "source" not in sig


@patch("scraper.sources.screener.ScreenerScraper.scrape_stock")
@patch("scraper.sources.trendlyne.TrendlyneScraper.scrape_stock")
def test_pipeline_signals_disabled_when_flagged(
    mock_trendlyne, mock_screener, temp_output_dir, mock_scraper_responses
):
    mock_screener.return_value = mock_scraper_responses["financial"]
    mock_trendlyne.return_value = mock_scraper_responses["profile"]
    run_ids = run_scraper(
        symbol="TEST",
        output_dir=temp_output_dir,
        persist_runs=True,
        signals=False,  # signals disabled
        shareholding=True,
        trendlyne=True,
    )
    assert len(run_ids) == 1
    repo = DataRepository(base_dir=temp_output_dir)
    latest = repo.get_latest("TEST")
    assert latest is not None
    # signals block should be absent when disabled
    assert "signals" not in latest


@patch("scraper.sources.screener.ScreenerScraper.scrape_stock")
@patch("scraper.sources.trendlyne.TrendlyneScraper.scrape_stock")
def test_pipeline_signals_with_prior_runs(
    mock_trendlyne, mock_screener, temp_output_dir, mock_scraper_responses
):
    # First run to establish history
    mock_screener.return_value = mock_scraper_responses["financial"]
    mock_trendlyne.return_value = mock_scraper_responses["profile"]
    run_scraper(
        symbol="TEST",
        output_dir=temp_output_dir,
        persist_runs=True,
        signals=True,
        shareholding=True,
        trendlyne=True,
    )
    # Second run with slightly different data to trigger delta logic
    altered_responses = {
        "financial": {
            "metadata": {"company_name": "TestCo", "sector": "Technology"},
            "financials": {
                "income_statement": {
                    "Revenue": [1100, 1200],
                    "Net Profit": [140, 160],
                },
                "balance_sheet": {
                    "Total Assets": [850, 900],
                },
                "cash_flow": {},
                "metrics": {
                    "Operating Margin": [0.127, 0.133],
                    "Net Margin": [0.127, 0.133],
                    "ROCE": [0.165, 0.178],
                },
            },
        },
        "shareholding": {
            "shareholding": {
                "promoter": 53.0,
                "institutional": 32.0,
                "retail": 15.0,
                "period": "2024-Q4",
            }
        },
        "profile": {
            "company_name": "TestCo",
            "sector": "Technology",
            "industry": "Software",
        },
    }
    mock_screener.return_value = altered_responses["financial"]
    run_ids = run_scraper(
        symbol="TEST",
        output_dir=temp_output_dir,
        persist_runs=True,
        signals=True,
        shareholding=True,
        trendlyne=True,
    )
    assert len(run_ids) == 1
    repo = DataRepository(base_dir=temp_output_dir)
    latest = repo.get_latest("TEST")
    assert latest is not None
    assert "signals" in latest
    signals_block = latest["signals"]
    assert "active" in signals_block
    # Should still have signals, possibly more nuanced due to delta
    assert len(signals_block["active"]) >= 1


@patch("scraper.sources.screener.ScreenerScraper.scrape_stock")
@patch("scraper.sources.trendlyne.TrendlyneScraper.scrape_stock")
def test_pipeline_regression_shareholding_and_validation_unaffected(
    mock_trendlyne, mock_screener, temp_output_dir, mock_scraper_responses
):
    mock_screener.return_value = mock_scraper_responses["financial"]
    mock_trendlyne.return_value = mock_scraper_responses["profile"]
    run_ids = run_scraper(
        symbol="TEST",
        output_dir=temp_output_dir,
        persist_runs=True,
        signals=True,
        shareholding=True,
        trendlyne=True,
    )
    assert len(run_ids) == 1
    repo = DataRepository(base_dir=temp_output_dir)
    latest = repo.get_latest("TEST")
    # Ensure shareholding block still present and sanitized
    assert "shareholding" in latest
    shareholding = latest["shareholding"]
    assert "status" in shareholding
    assert "summary" in shareholding
    assert "insights" in shareholding
    # Ensure validation block present
    assert "validation" in latest
    validation = latest["validation"]
    assert "status" in validation
    # Ensure fundametrics_response contains shareholding insights but not raw tables
    fundametrics = latest.get("fundametrics_response", {})
    assert "shareholding" in fundametrics
    assert "status" in fundametrics["shareholding"]
    # raw tables should not be present
    assert "shareholding_table" not in fundametrics
    assert "shareholding_snapshot" not in fundametrics
