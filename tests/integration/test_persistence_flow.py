import json
from pathlib import Path

from scraper.main import run_scraper


def _load_payload(base_dir: Path, symbol: str, run_id: str) -> dict:
    payload_path = base_dir / symbol.lower() / f"{run_id}.json"
    with payload_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_run_persists_shareholding_insights(tmp_path, mock_scraper_responses):
    symbol = "FUNDAMETRICS"

    run_ids = run_scraper(
        symbol=symbol,
        shareholding=True,
        trendlyne=True,
        persist_runs=True,
        output_dir=tmp_path,
    )

    assert run_ids, "run_scraper should return at least one run id"
    run_id = run_ids[0]

    payload = _load_payload(tmp_path, symbol, run_id)

    assert payload.get("symbol") == symbol

    shareholding = payload.get("shareholding")
    assert shareholding is not None, "Shareholding block missing from payload"

    status = shareholding.get("status")
    assert status in {"available", "unavailable", "partial"}

    insights = shareholding.get("insights")
    summary = shareholding.get("summary")

    if status == "available":
        assert isinstance(insights, dict)
        assert set(insights.keys()) == {
            "promoter_trend",
            "institutional_bias",
            "retail_risk",
            "ownership_stability_score",
        }
        assert summary is not None
    else:
        assert insights is None
        assert summary is None

    # fundametrics_response should contain API-facing insights block but no raw tables
    response = payload.get("fundametrics_response", {})
    api_insights = response.get("shareholding_insights")
    assert isinstance(api_insights, dict)
    assert set(api_insights.keys()) == {
        "promoter_trend",
        "institutional_bias",
        "retail_risk",
        "ownership_stability_score",
    }

    serialized = json.dumps(payload).lower()
    for forbidden in ("shareholding_pattern", "screener", "trendlyne", "external source"):
        assert forbidden not in serialized
