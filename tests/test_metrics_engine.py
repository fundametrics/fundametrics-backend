"""
Tests for Fundametrics Metrics Engine
Validates accuracy of proprietary metric calculations
"""

import pytest
from decimal import Decimal
from scraper.core.metrics_engine import FundametricsMetricsEngine


class TestFundametricsMetricsEngine:
    """Test suite for Fundametrics Metrics Engine calculations"""

    def test_calc_operating_margin(self):
        """Test operating margin calculation"""
        # Normal case
        result = FundametricsMetricsEngine.calc_operating_margin(1000, 200)
        assert result == 20.0
        
        # Zero revenue edge case
        result = FundametricsMetricsEngine.calc_operating_margin(0, 200)
        assert result is None
        
        # Negative operating profit
        result = FundametricsMetricsEngine.calc_operating_margin(1000, -100)
        assert result == -10.0

    def test_calc_net_margin(self):
        """Test net margin calculation"""
        # Normal case
        result = FundametricsMetricsEngine.calc_net_margin(1000, 150)
        assert result == 15.0
        
        # Zero revenue edge case
        result = FundametricsMetricsEngine.calc_net_margin(0, 150)
        assert result is None

    def test_calc_return_on_equity(self):
        """Test ROE calculation"""
        # Normal case
        result = FundametricsMetricsEngine.calc_return_on_equity(150, 1000)
        assert result == 15.0
        
        # Zero equity edge case
        result = FundametricsMetricsEngine.calc_return_on_equity(150, 0)
        assert result is None

    def test_calc_eps(self):
        """Test EPS calculation"""
        # Normal case
        result = FundametricsMetricsEngine.calc_eps(150000, 10000)
        assert result == 15.0
        
        # Zero shares edge case
        result = FundametricsMetricsEngine.calc_eps(150000, 0)
        assert result is None

    def test_calc_market_cap(self):
        """Test market cap calculation"""
        # Normal case
        result = FundametricsMetricsEngine.calc_market_cap(250, 1000000)
        assert result == 250000000
        
        # Missing inputs
        result = FundametricsMetricsEngine.calc_market_cap(0, 1000000)
        assert result is None
        result = FundametricsMetricsEngine.calc_market_cap(250, 0)
        assert result is None

    def test_compute_growth_rate(self):
        """Test growth rate calculation"""
        # Normal CAGR case
        result = FundametricsMetricsEngine.compute_growth_rate(100, 150, 2)
        assert round(result, 2) == 22.47
        
        # Zero start value edge case
        result = FundametricsMetricsEngine.compute_growth_rate(0, 150, 2)
        assert result is None
        
        # Negative end value edge case
        result = FundametricsMetricsEngine.compute_growth_rate(100, -50, 2)
        assert result is None

    def test_compute_fundametrics_metrics_basic(self):
        """Test basic Fundametrics metrics computation"""
        income_statement = {
            "FY2022": {"revenue": 1000, "operating_profit": 200, "net_income": 150},
            "FY2023": {"revenue": 1200, "operating_profit": 240, "net_income": 180}
        }
        
        engine = FundametricsMetricsEngine()
        metrics = engine.compute_fundametrics_metrics(
            income_statement=income_statement,
            shares_outstanding=1000,
            share_price=50
        )
        
        # Check required metrics are present
        assert "fundametrics_operating_margin" in metrics
        assert "fundametrics_eps" in metrics
        assert "fundametrics_market_cap" in metrics
        assert "fundametrics_growth_rate_internal" in metrics
        
        # Check values are computed correctly
        assert metrics["fundametrics_operating_margin"] == 20.0  # 240/1200 * 100
        assert metrics["fundametrics_eps"] == 0.18  # 180/1000
        assert metrics["fundametrics_market_cap"] == 50000  # 50 * 1000

    def test_compute_fundametrics_metrics_with_balance_sheet(self):
        """Test Fundametrics metrics with balance sheet data"""
        income_statement = {
            "FY2022": {"revenue": 1000, "operating_profit": 200, "net_income": 150},
            "FY2023": {"revenue": 1200, "operating_profit": 240, "net_income": 180}
        }
        balance_sheet = {
            "FY2022": {"equity_capital": 500, "reserves": 300},
            "FY2023": {"equity_capital": 550, "reserves": 350}
        }
        
        engine = FundametricsMetricsEngine()
        metrics = engine.compute_fundametrics_metrics(
            income_statement=income_statement,
            balance_sheet=balance_sheet
        )
        
        # Check ROE is computed with balance sheet
        assert "fundametrics_return_on_equity" in metrics
        # Average equity = (550+350 + 500+300) / 2 = 850
        # ROE = 180 / 850 * 100 = 21.18
        assert round(metrics["fundametrics_return_on_equity"], 2) == 21.18

    def test_analyze_company_history(self):
        """Test historical analysis functionality"""
        financials = {
            "FY2021": {"revenue": 800, "operating_profit": 160, "net_income": 120},
            "FY2022": {"revenue": 1000, "operating_profit": 200, "net_income": 150},
            "FY2023": {"revenue": 1200, "operating_profit": 240, "net_income": 180}
        }
        
        engine = FundametricsMetricsEngine()
        result = engine.analyze_company_history(financials)
        
        # Check structure
        assert "annual_metrics" in result
        assert "growth_metrics" in result
        assert "summary_metrics" in result
        
        # Check annual metrics
        assert "FY2021" in result["annual_metrics"]
        assert "FY2022" in result["annual_metrics"]
        assert "FY2023" in result["annual_metrics"]
        
        # Check growth metrics
        assert "fundametrics_revenue_growth_annualized" in result["growth_metrics"]
        assert "fundametrics_growth_rate_internal" in result["growth_metrics"]

    def test_period_sort_key(self):
        """Test period sorting functionality"""
        engine = FundametricsMetricsEngine()
        
        # Test valid year extraction
        assert engine._period_sort_key("FY2023") == 2023
        assert engine._period_sort_key("2022") == 2022
        assert engine._period_sort_key("Mar-2021") == 2021
        
        # Test invalid period
        assert engine._period_sort_key("invalid") == 0
        assert engine._period_sort_key("") == 0

    def test_empty_input_handling(self):
        """Test handling of empty or invalid inputs"""
        engine = FundametricsMetricsEngine()
        
        # Empty income statement
        metrics = engine.compute_fundametrics_metrics(income_statement={})
        # Should return template with None values for consistency
        expected_keys = {
            "fundametrics_operating_margin", "fundametrics_net_margin", "fundametrics_interest_coverage",
            "fundametrics_return_on_equity", "fundametrics_asset_turnover", "fundametrics_eps", 
            "fundametrics_market_cap", "fundametrics_growth_rate_internal"
        }
        assert set(metrics.keys()) == expected_keys
        assert all(value is None for value in metrics.values())
        
        # Empty financials for history
        result = engine.analyze_company_history({})
        assert result == {}
