import json
from pathlib import Path

from scraper.main import run_scraper


def _load_payload(base_dir: Path, symbol: str, run_id: str) -> dict:
    payload_path = base_dir / symbol.lower() / f"{run_id}.json"
    with payload_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_skip_shareholding_flag_degrades_cleanly(tmp_path, mock_scraper_responses):
    symbol = "FUNDAMETRICS"

    run_ids = run_scraper(
        symbol=symbol,
        shareholding=False,
        trendlyne=True,
        persist_runs=True,
        output_dir=tmp_path,
    )

    assert run_ids, "run_scraper should return at least one run id"
    run_id = run_ids[0]

    payload = _load_payload(tmp_path, symbol, run_id)

    shareholding = payload.get("shareholding")
    assert shareholding is not None
    assert shareholding.get("status") == "unavailable"
    assert shareholding.get("summary") is None
    assert shareholding.get("insights") is None

    assert "shareholding_insights" in payload.get("fundametrics_response", {})
    assert payload["fundametrics_response"].get("metadata", {}).get("shareholding_status") == "unavailable"
