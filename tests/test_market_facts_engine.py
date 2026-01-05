"""
Tests for MarketFactsEngine
"""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from scraper.core.market_facts_engine import MarketFactsEngine, MarketFacts


class TestMarketFactsEngine(unittest.TestCase):
    def setUp(self):
        self.fetcher_mock = Mock()
        self.engine = MarketFactsEngine(fetcher=self.fetcher_mock)

    def test_market_facts_dataclass(self):
        """Test MarketFacts dataclass structure."""
        timestamp = datetime.now(timezone.utc)
        facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15050.0,
            market_cap_currency="INR",
            last_updated=timestamp
        )
        
        self.assertEqual(facts.current_price, 150.50)
        self.assertEqual(facts.price_currency, "INR")
        self.assertEqual(facts.price_delay_minutes, 20)
        self.assertEqual(facts.fifty_two_week_high, 200.0)
        self.assertEqual(facts.fifty_two_week_low, 100.0)
        self.assertEqual(facts.shares_outstanding, 1000000.0)
        self.assertEqual(facts.market_cap, 15050.0)
        self.assertEqual(facts.market_cap_currency, "INR")
        self.assertEqual(facts.last_updated, timestamp)

    def test_compute_market_cap_valid_inputs(self):
        """Test market cap computation with valid inputs."""
        result = self.engine._compute_market_cap(150.0, 1000000.0)
        self.assertEqual(result, 15.0)  # 150 * 1000000 / 10000000 = 15 crores

    def test_compute_market_cap_invalid_inputs(self):
        """Test market cap computation with invalid inputs."""
        # None inputs
        self.assertIsNone(self.engine._compute_market_cap(None, 1000000.0))
        self.assertIsNone(self.engine._compute_market_cap(150.0, None))
        
        # Zero or negative inputs
        self.assertIsNone(self.engine._compute_market_cap(0.0, 1000000.0))
        self.assertIsNone(self.engine._compute_market_cap(-150.0, 1000000.0))
        self.assertIsNone(self.engine._compute_market_cap(150.0, 0.0))
        self.assertIsNone(self.engine._compute_market_cap(150.0, -1000000.0))

    def test_extract_float_valid_data(self):
        """Test float extraction from valid data."""
        data = {"price": "150.50", "volume": 1000000}
        self.assertEqual(self.engine._extract_float(data, "price"), 150.50)
        self.assertEqual(self.engine._extract_float(data, "volume"), 1000000.0)
        self.assertIsNone(self.engine._extract_float(data, "missing"))
        self.assertEqual(self.engine._extract_float(data, "missing", default=100.0), 100.0)

    def test_extract_float_exception_data(self):
        """Test float extraction from exception."""
        exception = ValueError("Test error")
        self.assertIsNone(self.engine._extract_float(exception, "price"))
        self.assertEqual(self.engine._extract_float(exception, "price", default=50.0), 50.0)

    def test_extract_int_valid_data(self):
        """Test integer extraction from valid data."""
        data = {"delay": "20", "shares": 1000000}
        self.assertEqual(self.engine._extract_int(data, "delay"), 20)
        self.assertEqual(self.engine._extract_int(data, "shares"), 1000000)
        self.assertEqual(self.engine._extract_int(data, "missing"), 0)
        self.assertEqual(self.engine._extract_int(data, "missing", default=10), 10)

    def test_extract_shares_valid_range(self):
        """Test shares extraction with valid range."""
        data = {"shares_outstanding": 1000000.0}
        self.assertEqual(self.engine._extract_shares(data), 1000000.0)
        
        # Test boundary values
        data_large = {"shares_outstanding": 99999999999.0}
        self.assertEqual(self.engine._extract_shares(data_large), 99999999999.0)

    def test_extract_shares_invalid_range(self):
        """Test shares extraction with invalid range."""
        # Zero or negative
        self.assertIsNone(self.engine._extract_shares({"shares_outstanding": 0.0}))
        self.assertIsNone(self.engine._extract_shares({"shares_outstanding": -1000.0}))
        
        # Too large
        self.assertIsNone(self.engine._extract_shares({"shares_outstanding": 100000000000.0}))
        
        # Exception
        self.assertIsNone(self.engine._extract_shares(ValueError("Error")))

    def test_build_market_block_complete_data(self):
        """Test building market block with complete data."""
        timestamp = datetime.now(timezone.utc)
        facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=timestamp
        )
        
        block = self.engine.build_market_block(facts)
        
        # Check price section
        self.assertEqual(block["price"]["value"], 150.50)
        self.assertEqual(block["price"]["currency"], "INR")
        self.assertEqual(block["price"]["delay_minutes"], 20)
        
        # Check 52-week range section
        self.assertEqual(block["range_52_week"]["high"], 200.0)
        self.assertEqual(block["range_52_week"]["low"], 100.0)
        self.assertEqual(block["range_52_week"]["currency"], "INR")
        
        # Check shares section
        self.assertEqual(block["shares_outstanding"]["value"], 1000000.0)
        self.assertEqual(block["shares_outstanding"]["currency"], "shares")
        
        # Check market cap section
        self.assertEqual(block["market_cap"]["value"], 15.05)
        self.assertEqual(block["market_cap"]["currency"], "INR")
        self.assertEqual(block["market_cap"]["computed"], "internal")
        
        # Check metadata
        self.assertEqual(block["metadata"]["source"], "public_market_data")
        self.assertEqual(block["metadata"]["data_type"], "facts_only")
        self.assertIn("delay_disclaimer", block["metadata"])
        self.assertIn("source_disclaimer", block["metadata"])
        self.assertIn("last_updated", block["metadata"])

    def test_build_market_block_partial_data(self):
        """Test building market block with partial/missing data."""
        facts = MarketFacts(
            current_price=None,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=None,
            fifty_two_week_low=None,
            shares_outstanding=None,
            market_cap=None,
            market_cap_currency="INR",
            last_updated=datetime.now(timezone.utc)
        )
        
        block = self.engine.build_market_block(facts)
        
        # Check that None values are preserved
        self.assertIsNone(block["price"]["value"])
        self.assertIsNone(block["range_52_week"]["high"])
        self.assertIsNone(block["range_52_week"]["low"])
        self.assertIsNone(block["shares_outstanding"]["value"])
        self.assertIsNone(block["market_cap"]["value"])
        
        # Check that metadata is still present
        self.assertEqual(block["metadata"]["source"], "public_market_data")
        self.assertEqual(block["metadata"]["data_type"], "facts_only")

    @patch('scraper.core.market_facts_engine.asyncio.gather')
    async def test_fetch_market_facts_success(self, gather_mock):
        """Test successful market facts fetching."""
        # Mock the gather results
        price_data = {"current_price": 150.50, "delay_minutes": 20}
        range_data = {"fifty_two_week_high": 200.0, "fifty_two_week_low": 100.0}
        shares_data = {"shares_outstanding": 1000000.0}
        
        gather_mock.return_value = [price_data, range_data, shares_data]
        
        facts = await self.engine.fetch_market_facts("BHEL")
        
        self.assertEqual(facts.current_price, 150.50)
        self.assertEqual(facts.price_delay_minutes, 20)
        self.assertEqual(facts.fifty_two_week_high, 200.0)
        self.assertEqual(facts.fifty_two_week_low, 100.0)
        self.assertEqual(facts.shares_outstanding, 1000000.0)
        self.assertEqual(facts.market_cap, 15.05)  # Computed internally
        self.assertEqual(facts.price_currency, "INR")
        self.assertEqual(facts.market_cap_currency, "INR")

    @patch('scraper.core.market_facts_engine.asyncio.gather')
    async def test_fetch_market_facts_with_exceptions(self, gather_mock):
        """Test market facts fetching with some exceptions."""
        # Mock the gather results with exceptions
        price_data = {"current_price": 150.50, "delay_minutes": 20}
        range_exception = ValueError("Network error")
        shares_exception = RuntimeError("API error")
        
        gather_mock.return_value = [price_data, range_exception, shares_exception]
        
        facts = await self.engine.fetch_market_facts("BHEL")
        
        # Should have price data but None for failed fetches
        self.assertEqual(facts.current_price, 150.50)
        self.assertEqual(facts.price_delay_minutes, 20)
        self.assertIsNone(facts.fifty_two_week_high)
        self.assertIsNone(facts.fifty_two_week_low)
        self.assertIsNone(facts.shares_outstanding)
        self.assertIsNone(facts.market_cap)  # Can't compute without shares

    def test_no_advisory_fields_in_market_block(self):
        """Test that no advisory/predictive fields are exposed."""
        timestamp = datetime.now(timezone.utc)
        facts = MarketFacts(
            current_price=150.50,
            price_currency="INR",
            price_delay_minutes=20,
            fifty_two_week_high=200.0,
            fifty_two_week_low=100.0,
            shares_outstanding=1000000.0,
            market_cap=15.05,
            market_cap_currency="INR",
            last_updated=timestamp
        )
        
        block = self.engine.build_market_block(facts)
        
        # Check that no advisory fields are present
        advisory_keywords = ["recommendation", "target", "forecast", "prediction", "advice", "buy", "sell", "hold"]
        
        def check_no_advisory(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    key_lower = key.lower()
                    for keyword in advisory_keywords:
                        self.assertNotIn(keyword, key_lower, f"Advisory keyword '{keyword}' found in key '{key}'")
                    if isinstance(value, (dict, list)):
                        check_no_advisory(value)
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        check_no_advisory(item)
        
        check_no_advisory(block)


if __name__ == "__main__":
    unittest.main()
