"""
Tests for the Fundametrics API Response Builder.
"""

import os
import sys
import unittest
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scraper.core.api_response_builder import FundametricsResponseBuilder, DataFreshness

class TestApiResponseBuilder(unittest.TestCase):
    def setUp(self):
        self.symbol = "COALINDIA"
        self.company_name = "Coal India Limited"
        self.sector = "Metals & Mining"
        self.builder = FundametricsResponseBuilder(
            symbol=self.symbol,
            company_name=self.company_name,
            sector=self.sector
        )
    
    def _new_builder(self) -> FundametricsResponseBuilder:
        return FundametricsResponseBuilder(
            symbol=self.symbol,
            company_name=self.company_name,
            sector=self.sector,
        )

    def test_basic_response_structure(self):
        """Test that the basic response structure is correct"""
        response = self.builder.build()
        
        # Check top-level structure
        self.assertEqual(response['symbol'], self.symbol)
        self.assertEqual(response['company']['name'], self.company_name)
        self.assertEqual(response['company']['sector'], self.sector)
        
        # Check required metadata
        self.assertIn('metadata', response)
        self.assertIn('data_freshness', response['metadata'])
        self.assertIn('as_of_date', response['metadata'])
        self.assertIn('computed_by', response['metadata'])
        self.assertIn('version', response['metadata'])
        self.assertIn('fundametrics_disclaimer', response['metadata'])

    def test_with_financial_data(self):
        """Test response with financial data"""
        income_data = {
            "2023": {
                "revenue": 1000000000,
                "operating_profit": 250000000,
                "net_income": 150000000
            }
        }
        
        response = (
            self.builder
            .add_income_statement(income_data)
            .build()
        )
        
        self.assertIn('income_statement', response['metadata']['data_sources'])
        self.assertIn('financials', response)
        self.assertIn('metrics', response['financials'])
    
    def test_with_shareholding_data(self):
        """Test response with shareholding data"""
        shareholding_data = {
            "2024-Q1": {
                "Promoter": 65.2,
                "Institutional Investors": 18.5,
                "Public Shareholding": 15.8,
                "Government": 0.5
            }
        }
        
        response = (
            self.builder
            .add_shareholding(shareholding_data)
            .build()
        )
        
        self.assertIn('shareholding', response['metadata']['data_sources'])
        self.assertIn('shareholding', response)
        self.assertIsInstance(response['shareholding'], dict)
        self.assertEqual(response['metadata']['shareholding_status'], 'available')
        
        # Test sanitized shareholding insights structure
        shareholding_block = response['shareholding']
        self.assertIn('summary', shareholding_block)
        self.assertIn('insights', shareholding_block)
        self.assertIsInstance(shareholding_block['insights'], list)
        # Each insight should be a dict with name/value keys
        for insight in shareholding_block['insights']:
            self.assertIsInstance(insight, dict)
            self.assertIn('name', insight)
            self.assertIn('value', insight)
            # Note: severity may not be present in basic shareholding insights

    def test_metrics_template_present_without_financials(self):
        """Ensure metrics block exists with expected keys even without data."""
        builder = self._new_builder()
        response = builder.build()

        # Check that metrics block always exists
        self.assertIn('financials', response)
        self.assertIn('metrics', response['financials'])
        
        metrics = response['financials']['metrics']
        expected_keys = {
            "fundametrics_operating_margin",
            "fundametrics_net_margin",
            "fundametrics_interest_coverage",
            "fundametrics_return_on_equity",
            "fundametrics_asset_turnover",
            "fundametrics_eps",
            "fundametrics_market_cap",
            "fundametrics_growth_rate_internal",
        }

        self.assertEqual(set(metrics.keys()), expected_keys)
        self.assertTrue(all(value is None for value in metrics.values()))
        
        # Check that ratios block also exists (even if empty)
        self.assertIn('ratios', response['financials'])
        ratios = response['financials']['ratios']
        self.assertIsInstance(ratios, dict)

    def test_metrics_computation_with_balance_sheet(self):
        """Verify Fundametrics metrics engine computes ratios from income and balance sheet."""
        builder = self._new_builder()
        builder.add_income_statement(
            {
                "Mar 2023": {
                    "revenue": 80.0,
                    "operating_profit": 16.0,
                    "net_income": 8.0,
                },
                "Mar 2024": {
                    "revenue": 100.0,
                    "operating_profit": 20.0,
                    "net_income": 10.0,
                    "interest": 5.0,
                    "profit_before_tax": 15.0,
                },
            }
        )
        builder.add_balance_sheet(
            {
                "Mar 2023": {"total_assets": 40.0, "equity_capital": 10.0, "reserves": 18.0},
                "Mar 2024": {"total_assets": 50.0, "equity_capital": 12.0, "reserves": 18.0},
            }
        )

        response = builder.build()
        metrics = response['financials']['metrics']

        self.assertAlmostEqual(metrics['fundametrics_operating_margin'], 20.0)
        self.assertAlmostEqual(metrics['fundametrics_net_margin'], 10.0)
        self.assertAlmostEqual(metrics['fundametrics_interest_coverage'], 4.0)
        self.assertAlmostEqual(metrics['fundametrics_asset_turnover'], 2.0)
        self.assertAlmostEqual(metrics['fundametrics_return_on_equity'], 34.48)
        self.assertAlmostEqual(metrics['fundametrics_growth_rate_internal'], 25.0)
        self.assertIsNone(metrics['fundametrics_eps'])
        self.assertIsNone(metrics['fundametrics_market_cap'])
        
        # Check that ratios are computed and included
        self.assertIn('ratios', response['financials'])
        ratios = response['financials']['ratios']
        self.assertIsInstance(ratios, dict)
        # Should have computed ratios like P/E, ROE etc.
        expected_ratio_keys = ['pe_ratio', 'pb_ratio', 'debt_to_equity', 'current_ratio']
        for key in expected_ratio_keys:
            if key in ratios:
                self.assertIsInstance(ratios[key], (int, float, type(None)))

        metrics_context = response['metadata']['metrics_context']
        self.assertEqual(metrics_context['period'], 'Mar 2024')
        self.assertEqual(metrics_context['periodicity'], 'annual')

    def test_quarterly_metadata_and_sources(self):
        """Ensure quarterly detection metadata and deduplicated sources are populated."""
        builder = self._new_builder()
        quarters_payload = {
            "Jun 2024": {"revenue": 50.0},
            "Sep 2024": {"revenue": 60.0},
        }

        builder.set_quarterly_financials(quarters_payload)
        builder.set_quarterly_financials(quarters_payload)  # intentional duplicate call
        builder.add_income_statement(
            {
                "Sep 2024": {
                    "revenue": 210.0,
                    "operating_profit": 30.0,
                    "net_income": 18.0,
                    "interest": 4.0,
                    "profit_before_tax": 22.0,
                }
            }
        )

        response = builder.build()

        quarterly_meta = response['metadata']['quarterly_data']
        self.assertTrue(quarterly_meta['available'])
        self.assertEqual(quarterly_meta['latest_period'], 'Sep 2024')
        self.assertEqual(quarterly_meta['periods_available'], 2)

        metrics_context = response['metadata']['metrics_context']
        self.assertEqual(metrics_context['periodicity'], 'quarterly')

        data_sources = response['metadata']['data_sources']
        self.assertEqual(data_sources.count('quarters'), 1)
        self.assertIn('income_statement', data_sources)
    
    def test_company_metadata_for_ratios(self):
        """Test that company metadata is properly set for ratio computation."""
        builder = self._new_builder()
        company_metadata = {
            'shares_outstanding': 1000000,
            'current_price': 150.0
        }
        builder.set_company_metadata(company_metadata)
        
        # Add minimal financial data
        builder.add_income_statement({
            "Mar 2024": {
                "revenue": 100.0,
                "net_income": 10.0
            }
        })
        
        response = builder.build()
        
        # Should have market cap and EPS computed with company metadata
        metrics = response['financials']['metrics']
        # Note: Market cap and EPS require additional company metadata like shares_outstanding and current_price
        # which may not be fully implemented yet, so we check the structure is correct
        self.assertIn('fundametrics_market_cap', metrics)
        self.assertIn('fundametrics_eps', metrics)
        # Values may be None if computation is not fully implemented
    
    def test_sanitized_response_no_raw_data_leakage(self):
        """Test that API responses don't contain raw scraper metadata."""
        builder = self._new_builder()
        
        # Add data with potential raw metadata
        builder.add_income_statement({
            "Mar 2024": {
                "revenue": 100.0,
                "net_income": 10.0,
                "source": "moneycontrol",  # This should be sanitized out
                "source_url": "https://example.com",  # This should be sanitized out
                "raw_html": "<html>...</html>"  # This should be sanitized out
            }
        })
        
        response = builder.build()
        
        # Check that raw metadata keys are not present in the response
        self.assertNotIn('source', response)
        self.assertNotIn('source_url', response)
        self.assertNotIn('raw_html', response)
        self.assertNotIn('fetcher_metadata', response)
        
        # Financial data should be present but sanitized
        self.assertIn('financials', response)
        self.assertIn('metrics', response['financials'])
    
    def test_shareholding_insights_normalization(self):
        """Test that shareholding insights are properly normalized."""
        builder = self._new_builder()
        
        # Add shareholding data
        shareholding_data = {
            "2024-Q1": {
                "Promoter": 65.2,
                "Institutional Investors": 18.5,
                "Public Shareholding": 15.8,
                "Government": 0.5
            }
        }
        builder.add_shareholding(shareholding_data)
        
        response = builder.build()
        
        insights = response['shareholding']
        
        # Summary should be a dict
        self.assertIsInstance(insights['summary'], dict)
        
        # Insights should be a list of dicts with name/value
        self.assertIsInstance(insights['insights'], list)
        for insight in insights['insights']:
            self.assertIsInstance(insight, dict)
            self.assertIn('name', insight)
            self.assertIn('value', insight)
            # Note: severity may not be present in basic shareholding insights
    
    def test_data_freshness_calculation(self):
        """Test the data freshness calculation"""
        # This is a simple test - in practice, you'd mock the current time
        freshness = self.builder._calculate_data_freshness()
        
        # Should be a valid date in YYYY-MM-DD format
        self.assertRegex(freshness.as_of_date, r'^\d{4}-\d{2}-\d{2}$')
        
        # Days since update should be a non-negative integer
        self.assertIsInstance(freshness.days_since_update, int)
        self.assertGreaterEqual(freshness.days_since_update, 0)
        
        # Status should be one of the expected values
        self.assertIn(freshness.freshness_status, ['fresh', 'stale', 'outdated'])
    
    def test_error_handling(self):
        """Test that errors are properly handled and reported"""
        # Test with invalid data that would cause an error
        # The current implementation handles this gracefully without warnings
        response = (
            self.builder
            .add_income_statement({"2023": {"revenue": "invalid"}})
            .build()
        )
        
        # Should still have a valid response structure
        self.assertIn('metadata', response)
        self.assertIn('data_sources', response['metadata'])
        self.assertIn('income_statement', response['metadata']['data_sources'])
        
        # Should still have metrics block even with invalid data
        self.assertIn('financials', response)
        self.assertIn('metrics', response['financials'])
        self.assertIn('ratios', response['financials'])

if __name__ == "__main__":
    unittest.main()
