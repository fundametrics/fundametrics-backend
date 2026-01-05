import pytest

def _sample_shareholding():
    return {
        "2024-Q1": {
            "Promoter": 65.0,
            "Institutional": 20.0,
            "Public": 10.0,
            "Other": 5.0,
        },
        "2024-Q2": {
            "Promoter": 63.0,
            "Institutional": 22.0,
            "Public": 12.0,
            "Other": 3.0,
        },
        "2024-Q3": {
            "Promoter": 61.0,
            "Institutional": 24.0,
            "Public": 13.7,
            "Other": 1.3,
        },
    }


@pytest.fixture
def mock_scraper_responses(monkeypatch):
    """Stub external scrapers so tests can run without network access."""
    from scraper.main import ScreenerScraper, TrendlyneScraper

    shareholding = _sample_shareholding()

    async def fake_screener(self, symbol: str):
        return {
            "metadata": {
                "company_name": "Fundametrics Test Co",
                "symbol": symbol,
                "website_url": "https://fundametrics.example.com",
            },
            "financials": {
                "income_statement": {
                    "2024-Q3": {
                        "revenue": 1200.0,
                        "operating_profit": 240.0,
                        "net_income": 180.0,
                    },
                },
                "balance_sheet": {
                    "2024-Q3": {
                        "total_assets": 3000.0,
                    }
                },
            },
            "shareholding": shareholding,
        }

    async def fake_trendlyne(self, symbol: str):
        return {
            "company_name": "Fundametrics Test Co",
            "sector": "Technology",
        }

    monkeypatch.setattr(ScreenerScraper, "scrape_stock", fake_screener)
    monkeypatch.setattr(TrendlyneScraper, "scrape_stock", fake_trendlyne)

    return shareholding
