"""
Tests for API market data contract
"""

import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scraper.api.routes import router
from scraper.core.market_facts_engine import MarketFacts


class TestMarketAPIContract(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(router)

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_api_contract(self, mock_fetch):
        """Test that API exposes market facts with proper contract validation."""
        # Mock market facts
        mock_facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        response = self.client.get("/stocks/BHEL/market")
        
        # Check response structure
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check top-level structure
        self.assertEqual(data["symbol"], "BHEL")
        self.assertIn("market", data)
        self.assertIn("api_contract", data)
        
        # Check API contract validation
        contract = data["api_contract"]
        self.assertEqual(contract["data_type"], "facts_only")
        self.assertTrue(contract["no_advisory_content"])
        self.assertTrue(contract["delay_disclosed"])
        self.assertTrue(contract["disclaimer_included"])
        self.assertIn("last_updated", contract)
        
        # Check market block structure
        market = data["market"]
        self.assertIn("price", market)
        self.assertIn("range_52_week", market)
        self.assertIn("shares_outstanding", market)
        self.assertIn("market_cap", market)
        self.assertIn("metadata", market)
        
        # Check price structure
        price = market["price"]
        self.assertEqual(price["value"], 150.50)
        self.assertEqual(price["currency"], "INR")
        self.assertEqual(price["delay_minutes"], 20)
        
        # Check 52-week range structure
        range_52w = market["range_52_week"]
        self.assertEqual(range_52w["high"], 200.0)
        self.assertEqual(range_52w["low"], 100.0)
        self.assertEqual(range_52w["currency"], "INR")
        
        # Check shares outstanding structure
        shares = market["shares_outstanding"]
        self.assertEqual(shares["value"], 1000000.0)
        self.assertEqual(shares["currency"], "shares")
        
        # Check market cap structure
        market_cap = market["market_cap"]
        self.assertEqual(market_cap["value"], 15.05)
        self.assertEqual(market_cap["currency"], "INR")
        self.assertEqual(market_cap["computed"], "internal")
        
        # Check metadata structure
        metadata = market["metadata"]
        self.assertEqual(metadata["source"], "public_market_data")
        self.assertEqual(metadata["data_type"], "facts_only")
        self.assertIn("delay_disclaimer", metadata)
        self.assertIn("source_disclaimer", metadata)
        self.assertIn("last_updated", metadata)

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_no_advisory_content(self, mock_fetch):
        """Test that no advisory content is present in API response."""
        mock_facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        response = self.client.get("/stocks/BHEL/market")
        data = response.json()
        
        # Check for advisory keywords
        advisory_keywords = [
            "recommendation", "target", "forecast", "prediction", "advice", 
            "buy", "sell", "hold", "rating", "outperform", "underperform"
        ]
        
        def check_no_advisory(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = key.lower()
                    value_str = str(value).lower() if value else ""
                    
                    for keyword in advisory_keywords:
                        self.assertNotIn(keyword, key_lower, 
                                       f"Advisory keyword '{keyword}' found in key '{path}.{key}'")
                        self.assertNotIn(keyword, value_str,
                                       f"Advisory keyword '{keyword}' found in value at '{path}.{key}'")
                    
                    if isinstance(value, (dict, list)):
                        check_no_advisory(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        check_no_advisory(item, f"{path}[{i}]" if path else f"[{i}]")
        
        check_no_advisory(data)

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_explicit_delay_disclosure(self, mock_fetch):
        """Test that delay is explicitly disclosed in API response."""
        mock_facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        response = self.client.get("/stocks/BHEL/market")
        data = response.json()
        
        # Check delay disclosure in multiple places
        market = data["market"]
        
        # Price section should show delay
        self.assertIn("delay_minutes", market["price"])
        self.assertEqual(market["price"]["delay_minutes"], 20)
        
        # Metadata should have delay disclaimer
        self.assertIn("delay_disclaimer", market["metadata"])
        delay_disclaimer = market["metadata"]["delay_disclaimer"]
        self.assertIn("delayed", delay_disclaimer.lower())
        self.assertIn("minutes", delay_disclaimer.lower())
        
        # API contract should indicate delay disclosed
        self.assertTrue(data["api_contract"]["delay_disclosed"])

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_explicit_disclaimer(self, mock_fetch):
        """Test that disclaimer is explicitly included in API response."""
        mock_facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        response = self.client.get("/stocks/BHEL/market")
        data = response.json()
        
        # Check disclaimer in metadata
        market = data["market"]
        metadata = market["metadata"]
        
        self.assertIn("delay_disclaimer", metadata)
        self.assertIn("source_disclaimer", metadata)
        
        # Check disclaimer content
        delay_disclaimer = metadata["delay_disclaimer"]
        source_disclaimer = metadata["source_disclaimer"]
        
        self.assertIn("informational purposes", delay_disclaimer.lower())
        self.assertIn("trading decisions", delay_disclaimer.lower())
        self.assertIn("accuracy cannot be guaranteed", source_disclaimer.lower())
        
        # API contract should indicate disclaimer included
        self.assertTrue(data["api_contract"]["disclaimer_included"])

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_partial_data_handling(self, mock_fetch):
        """Test API handling of partial/missing market data."""
        mock_facts = MarketFacts(
            current_price=None,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=None,
            fifty_two_week_low=None,
            shares_outstanding=None,
            market_cap=None,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        response = self.client.get("/stocks/BHEL/market")
        data = response.json()
        
        # Check that None values are preserved
        market = data["market"]
        self.assertIsNone(market["price"]["value"])
        self.assertIsNone(market["range_52_week"]["high"])
        self.assertIsNone(market["range_52_week"]["low"])
        self.assertIsNone(market["shares_outstanding"]["value"])
        self.assertIsNone(market["market_cap"]["value"])
        
        # Check that structure is still maintained
        self.assertIn("price", market)
        self.assertIn("range_52_week", market)
        self.assertIn("shares_outstanding", market)
        self.assertIn("market_cap", market)
        self.assertIn("metadata", market)

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_symbol_case_normalization(self, mock_fetch):
        """Test that symbol is normalized to uppercase."""
        mock_facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=None
        )
        mock_fetch.return_value = mock_facts

        # Test lowercase input
        response = self.client.get("/stocks/bhel/market")
        data = response.json()
        self.assertEqual(data["symbol"], "BHEL")
        
        # Test mixed case input
        response = self.client.get("/stocks/Bhel/market")
        data = response.json()
        self.assertEqual(data["symbol"], "BHEL")

    @patch('scraper.api.routes.market_engine.fetch_market_facts')
    async def test_market_facts_error_handling(self, mock_fetch):
        """Test API error handling for market facts."""
        mock_fetch.side_effect = Exception("Network error")
        
        response = self.client.get("/stocks/BHEL/market")
        
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to fetch market facts", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
