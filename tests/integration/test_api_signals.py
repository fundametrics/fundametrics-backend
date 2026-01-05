import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from scraper.api.app import app
from scraper.core.repository import DataRepository


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_payload_with_signals():
    return {
        "symbol": "TEST",
        "run_id": "r1",
        "run_timestamp": "2025-01-01T12:00:00Z",
        "validation": {"status": "ok"},
        "data": {},
        "metrics": {},
        "fundametrics_response": {
            "symbol": "TEST",
            "metadata": {
                "run_id": "r1",
                "run_timestamp": "2025-01-01T12:00:00Z",
                "validation_status": "ok",
                "provenance": {"generated_by": "fundametrics"},
            },
            "shareholding": {"status": "ok", "insights": []},
            "signals": {
                "active": [
                    {
                        "signal": "margin_expansion/compression",
                        "severity": "medium",
                        "confidence": 0.65,
                        "explanation": "Margins improved YoY",
                        "generated_at": "2025-01-01T12:00:00Z",
                    },
                    {
                        "signal": "promoter_exit_warning",
                        "severity": "low",
                        "confidence": 0.2,
                        "explanation": "Promoter holdings stable",
                        "generated_at": "2025-01-01T12:00:00Z",
                    },
                ],
                "generated_at": "2025-01-01T12:00:00Z",
            },
        },
        "provenance": {"generated_by": "fundametrics"},
        "shareholding": {"status": "ok"},
        "signals": {
            "active": [
                {
                    "signal": "margin_expansion/compression",
                    "severity": "medium",
                    "confidence": 0.65,
                    "explanation": "Margins improved YoY",
                    "generated_at": "2025-01-01T12:00:00Z",
                },
                {
                    "signal": "promoter_exit_warning",
                    "severity": "low",
                    "confidence": 0.2,
                    "explanation": "Promoter holdings stable",
                    "generated_at": "2025-01-01T12:00:00Z",
                },
            ],
            "generated_at": "2025-01-01T12:00:00Z",
        },
    }


@pytest.fixture
def mock_payload_without_signals():
    payload = {
        "symbol": "TEST",
        "run_id": "r2",
        "run_timestamp": "2025-01-02T12:00:00Z",
        "validation": {"status": "ok"},
        "data": {},
        "metrics": {},
        "fundametrics_response": {
            "symbol": "TEST",
            "metadata": {
                "run_id": "r2",
                "run_timestamp": "2025-01-02T12:00:00Z",
                "validation_status": "ok",
                "provenance": {"generated_by": "fundametrics"},
            },
            "shareholding": {"status": "ok", "insights": []},
        },
        "provenance": {"generated_by": "fundametrics"},
        "shareholding": {"status": "ok"},
    }
    # No signals block
    return payload


@patch.object(DataRepository, "get_latest")
def test_api_returns_signals_when_enabled(mock_get_latest, client, mock_payload_with_signals):
    mock_get_latest.return_value = mock_payload_with_signals
    response = client.get("/stocks/TEST")
    assert response.status_code == 200
    body = response.json()
    assert "signals" in body
    signals = body["signals"]
    assert "active" in signals
    assert isinstance(signals["active"], list)
    assert len(signals["active"]) == 2
    # Verify structure of each signal
    for sig in signals["active"]:
        assert "signal" in sig
        assert "severity" in sig
        assert "confidence" in sig
        assert "explanation" in sig
        assert "generated_at" in sig
        # Ensure no internal leakage
        assert "raw_snapshot" not in sig
        assert "source" not in sig


@patch.object(DataRepository, "get_latest")
def test_api_omits_signals_when_disabled_via_payload(mock_get_latest, client, mock_payload_without_signals):
    mock_get_latest.return_value = mock_payload_without_signals
    response = client.get("/stocks/TEST")
    assert response.status_code == 200
    body = response.json()
    # signals block should be absent
    assert "signals" not in body


@patch.object(DataRepository, "get_latest")
@patch("scraper.api.routes.Config")
def test_api_respects_config_toggle(mock_config, mock_get_latest, client, mock_payload_with_signals):
    # Pretend signals disabled in config
    mock_config.get.return_value = False
    mock_get_latest.return_value = mock_payload_with_signals
    response = client.get("/stocks/TEST")
    assert response.status_code == 200
    body = response.json()
    # Since config disables signals, API should not expose them even if payload contains them
    assert "signals" not in body


@patch.object(DataRepository, "get_latest")
def test_api_signals_sanitized(mock_get_latest, client, mock_payload_with_signals):
    # Inject a malicious internal field into persisted payload to verify sanitization
    tainted_payload = json.loads(json.dumps(mock_payload_with_signals))
    tainted_payload["fundametrics_response"]["signals"]["active"][0]["internal_debug"] = {"raw": "data"}
    mock_get_latest.return_value = tainted_payload
    response = client.get("/stocks/TEST")
    assert response.status_code == 200
    body = response.json()
    signals = body["signals"]
    assert "active" in signals
    sig = signals["active"][0]
    # internal_debug should be stripped
    assert "internal_debug" not in sig


def test_api_signals_missing_symbol(client):
    response = client.get("/stocks/NONEXISTENT")
    assert response.status_code == 404


@patch.object(DataRepository, "get_latest")
def test_api_signals_empty_list(mock_get_latest, client):
    empty_payload = {
        "symbol": "EMPTY",
        "run_id": "e1",
        "run_timestamp": "2025-01-01T12:00:00Z",
        "validation": {"status": "ok"},
        "data": {},
        "metrics": {},
        "fundametrics_response": {
            "symbol": "EMPTY",
            "metadata": {
                "run_id": "e1",
                "run_timestamp": "2025-01-01T12:00:00Z",
                "validation_status": "ok",
                "provenance": {"generated_by": "fundametrics"},
            },
            "shareholding": {"status": "ok", "insights": []},
            "signals": {"active": [], "generated_at": "2025-01-01T12:00:00Z"},
        },
        "provenance": {"generated_by": "fundametrics"},
        "shareholding": {"status": "ok"},
        "signals": {"active": [], "generated_at": "2025-01-01T12:00:00Z"},
    }
    mock_get_latest.return_value = empty_payload
    response = client.get("/stocks/EMPTY")
    assert response.status_code == 200
    body = response.json()
    assert "signals" in body
    assert body["signals"]["active"] == []
