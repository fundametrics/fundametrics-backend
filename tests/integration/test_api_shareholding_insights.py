from fastapi.testclient import TestClient

from scraper.api import routes
from scraper.api.app import app
from scraper.core.repository import DataRepository
from scraper.main import run_scraper


def test_api_exposes_shareholding_insights_only(tmp_path, mock_scraper_responses, monkeypatch):
    symbol = "FUNDAMETRICS"

    run_ids = run_scraper(
        symbol=symbol,
        shareholding=True,
        trendlyne=True,
        persist_runs=True,
        output_dir=tmp_path,
    )
    assert run_ids

    monkeypatch.setattr(routes, "repo", DataRepository(base_dir=tmp_path))

    client = TestClient(app)
    response = client.get(f"/stocks/{symbol}")
    assert response.status_code == 200

    payload = response.json()

    assert "shareholding_insights" not in payload

    shareholding = payload.get("shareholding")
    assert shareholding is not None
    assert shareholding["status"] == "ok"

    insights = shareholding.get("insights")
    assert isinstance(insights, dict)
    assert set(insights.keys()) == {
        "promoter_trend",
        "institutional_bias",
        "retail_risk",
        "ownership_stability_score",
    }

    serialized = response.text.lower()
    assert "summary" not in serialized
    assert "shareholding_pattern" not in serialized


def test_api_respects_shareholding_skip(tmp_path, mock_scraper_responses, monkeypatch):
    symbol = "FUNDAMETRICS"

    run_ids = run_scraper(
        symbol=symbol,
        shareholding=False,
        trendlyne=True,
        persist_runs=True,
        output_dir=tmp_path,
    )
    assert run_ids

    monkeypatch.setattr(routes, "repo", DataRepository(base_dir=tmp_path))

    client = TestClient(app)
    response = client.get(f"/stocks/{symbol}")
    assert response.status_code == 200

    payload = response.json()
    shareholding = payload.get("shareholding")
    assert shareholding is not None
    assert shareholding["status"] == "unavailable"
    assert shareholding.get("insights") is None
