import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scraper.api.app import app  # noqa: E402
from scraper.api import routes  # noqa: E402


class TestSearchAPI:
    def setup_method(self):
        self.client = TestClient(app)

    def test_empty_query_returns_all(self, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.list_symbols.return_value = ["RELIANCE", "TCS"]
        mock_repo.get_latest.side_effect = [
            {
                "fundametrics_response": {
                    "company": {
                        "name": "Reliance Industries Limited",
                        "sector": "Energy",
                    }
                }
            },
            {
                "fundametrics_response": {
                    "company": {
                        "name": "Tata Consultancy Services",
                        "sector": "IT Services",
                    }
                }
            },
        ]

        monkeypatch.setattr(routes, "repo", mock_repo)

        response = self.client.get("/search")
        assert response.status_code == 200
        payload = response.json()

        assert payload["query"] == ""
        assert payload["disclaimer"]
        assert len(payload["results"]) == 2
        assert payload["results"][0] == {
            "symbol": "RELIANCE",
            "name": "Reliance Industries Limited",
            "sector": "Energy",
        }

    def test_filters_by_query(self, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.list_symbols.return_value = ["RELIANCE", "TCS", "HDFC"]
        mock_repo.get_latest.side_effect = [
            {
                "fundametrics_response": {
                    "company": {
                        "name": "Reliance Industries Limited",
                        "sector": "Energy",
                    }
                }
            },
            {
                "fundametrics_response": {
                    "company": {
                        "name": "Tata Consultancy Services",
                        "sector": "IT Services",
                    }
                }
            },
            None,
        ]

        monkeypatch.setattr(routes, "repo", mock_repo)

        response = self.client.get("/search", params={"query": "tcs"})
        assert response.status_code == 200
        payload = response.json()

        assert payload["query"] == "tcs"
        assert len(payload["results"]) == 1
        assert payload["results"][0]["symbol"] == "TCS"

    def test_handles_missing_company_block(self, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.list_symbols.return_value = ["ABC", "XYZ"]
        mock_repo.get_latest.side_effect = [
            {},
            {
                "fundametrics_response": {
                    "company": {
                        "name": "XYZ Corp",
                    }
                }
            },
        ]

        monkeypatch.setattr(routes, "repo", mock_repo)

        response = self.client.get("/search")
        assert response.status_code == 200
        payload = response.json()

        assert len(payload["results"]) == 1
        assert payload["results"][0]["symbol"] == "XYZ"
        assert payload["results"][0]["sector"] == "Not disclosed"
