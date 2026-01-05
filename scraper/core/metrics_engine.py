"""
Fundametrics Metrics Engine - Internal Analytics Layer
================================================

Computes all financial ratios, margins, and growth metrics internally 
using raw financial facts. This ensures Fundametrics owns its logic and 
presentation layer, separate from scraped analysis.
"""

from typing import Any, Dict, List, Optional
import re
from datetime import datetime, timezone

from scraper.core.metrics import MetricValue
from scraper.core.validators import MetricConsistencyError, validate_same_statement
from scraper.core.confidence import compute_confidence


class FundametricsMetricsEngine:
    """
    Engine for computing financial metrics from raw facts.
    Uses Fundametrics internal formulas.
    """

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _source_from_statement_id(statement_id: Optional[str], *, computed: bool) -> str:
        if statement_id:
            token = statement_id.upper()
            if "_NSE_" in token or "_BSE_" in token:
                return "exchange"
        return "derived" if computed else "aggregator"

    @staticmethod
    def _statement_status(inputs: List[MetricValue]) -> Optional[str]:
        if not inputs:
            return None
        ids = [metric.statement_id for metric in inputs if metric and metric.statement_id]
        none_present = any(metric is None or metric.statement_id is None for metric in inputs)
        if not ids:
            return "partial" if none_present else None
        unique = set(ids)
        if len(unique) == 1:
            return "partial" if none_present else "matched"
        return "inconsistent"

    @staticmethod
    def _completeness_state(inputs: List[MetricValue]) -> Optional[str]:
        if not inputs:
            return None
        total = len(inputs)
        present = sum(1 for metric in inputs if metric.value is not None)
        if present == 0:
            return "missing"
        if present == total:
            return "complete"
        return "partial"

    def _seed_confidence(
        self,
        metric: MetricValue,
        *,
        metadata: Optional[Dict[str, Any]],
        inputs: Optional[List[MetricValue]] = None,
        stability: Optional[object] = None,
    ) -> MetricValue:
        inputs = inputs or []
        context: Dict[str, Any] = {}
        source_type = self._source_from_statement_id(metric.statement_id, computed=metric.computed)
        if source_type:
            context["source_type"] = source_type
        metadata = metadata or {}
        generated_raw = metadata.get("generated")
        if generated_raw is not None:
            context["generated_at"] = generated_raw
        ttl_hours = metadata.get("ttl_hours")
        if ttl_hours is not None:
            context["ttl_hours"] = ttl_hours
        freshness_ratio = None
        if generated_raw is not None and ttl_hours:
            parsed = None
            if isinstance(generated_raw, datetime):
                parsed = generated_raw
            elif isinstance(generated_raw, str):
                try:
                    parsed = datetime.fromisoformat(generated_raw)
                except ValueError:
                    parsed = None
            try:
                ttl_numeric = float(ttl_hours)
            except (TypeError, ValueError):
                ttl_numeric = None
            if parsed and ttl_numeric and ttl_numeric > 0:
                age_hours = (self._now() - parsed).total_seconds() / 3600
                freshness_ratio = max(0.0, age_hours / ttl_numeric)
        if freshness_ratio is not None:
            context["freshness_ratio"] = freshness_ratio
        status_inputs = inputs + [metric]
        status = self._statement_status(status_inputs)
        if status:
            context["statement_status"] = status
        completeness = self._completeness_state(inputs)
        if completeness:
            context["completeness"] = completeness
        if inputs:
            total = len(inputs)
            present = sum(1 for item in inputs if item and item.value is not None)
            if total:
                context["completeness_ratio"] = present / total
        if stability is not None:
            context["stability"] = stability

        metric.confidence_inputs = context
        metric.confidence = compute_confidence(metric, None, self._now())
        return metric

    @staticmethod
    def _metric_missing(unit: str, reason: str) -> MetricValue:
        return MetricValue(
            value=None,
            unit=unit,
            statement_id=None,
            computed=True,
            reason=reason,
        )

    @staticmethod
    def _coerce_metric(value: Any, unit: str, *, reason: str = "Unavailable") -> MetricValue:
        if isinstance(value, MetricValue):
            return value
        if value is None:
            return FundametricsMetricsEngine._metric_missing(unit, reason)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return FundametricsMetricsEngine._metric_missing(unit, reason)
        return MetricValue(
            value=numeric,
            unit=unit,
            statement_id=None,
            computed=False,
        )

    @staticmethod
    def _sum_metrics(metrics: List[MetricValue], unit: str, *, reason: str) -> MetricValue:
        base: Optional[MetricValue] = None
        total = 0.0
        try:
            for metric in metrics:
                if metric.value is None:
                    raise ValueError("Insufficient data")
                if base is None:
                    base = metric
                else:
                    validate_same_statement(base, metric)
                total += metric.value
            if base is None:
                raise ValueError("No metrics provided")
            return MetricValue(
                value=round(total, 2),
                unit=unit,
                statement_id=base.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError):
            return FundametricsMetricsEngine._metric_missing(unit, reason)

    @staticmethod
    def _first_metric(data: Dict[str, Any], keys: list[str], unit: str, *, reason: str) -> MetricValue:
        for key in keys:
            if key in data:
                metric = FundametricsMetricsEngine._coerce_metric(data.get(key), unit, reason=reason)
                if metric.value is not None:
                    return metric
        return FundametricsMetricsEngine._metric_missing(unit, reason)

    @staticmethod
    def _period_sort_key(period: str) -> int:
        """Extract year component for chronological sorting."""
        if not period:
            return 0
        if "TTM" in str(period).upper():
            return 9999
        match = re.search(r"(\d{4})", str(period))
        return int(match.group(1)) if match else 0

    @staticmethod
    def calc_operating_margin(revenue: MetricValue, operating_profit: MetricValue) -> MetricValue:
        try:
            validate_same_statement(revenue, operating_profit)
            if revenue.value in (None, 0) or operating_profit.value is None:
                raise ValueError("Insufficient data")
            value = round((operating_profit.value / revenue.value) * 100, 2)
            return MetricValue(
                value=value,
                unit="%",
                statement_id=revenue.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = str(err)
            if isinstance(err, MetricConsistencyError):
                reason = "Cross-statement mismatch"
            return MetricValue(
                value=None,
                unit="%",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_net_margin(revenue: MetricValue, net_income: MetricValue) -> MetricValue:
        try:
            validate_same_statement(revenue, net_income)
            if revenue.value in (None, 0) or net_income.value is None:
                raise ValueError("Insufficient data")
            value = round((net_income.value / revenue.value) * 100, 2)
            return MetricValue(
                value=value,
                unit="%",
                statement_id=revenue.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = str(err)
            if isinstance(err, MetricConsistencyError):
                reason = "Cross-statement mismatch"
            return MetricValue(
                value=None,
                unit="%",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_roce(ebit: MetricValue, capital_employed: MetricValue) -> MetricValue:
        """Fundametrics Return on Capital Employed Calculation"""
        try:
            validate_same_statement(ebit, capital_employed)
            if capital_employed.value in (None, 0) or ebit.value is None:
                raise ValueError("Insufficient data")
            value = round((ebit.value / capital_employed.value) * 100, 2)
            return MetricValue(
                value=value,
                unit="%",
                statement_id=ebit.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="%",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_asset_turnover(revenue: MetricValue, total_assets: MetricValue) -> MetricValue:
        """Fundametrics Asset Turnover Calculation"""
        try:
            validate_same_statement(revenue, total_assets)
            if total_assets.value in (None, 0) or revenue.value is None:
                raise ValueError("Insufficient data")
            value = round(revenue.value / total_assets.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=revenue.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="x",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_interest_coverage(ebit: MetricValue, interest: MetricValue) -> MetricValue:
        """Fundametrics Interest Coverage Ratio Calculation"""
        try:
            validate_same_statement(ebit, interest)
            if interest.value in (None, 0) or ebit.value is None:
                raise ValueError("Insufficient data")
            value = round(ebit.value / interest.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=ebit.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="x",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_return_on_equity(net_income: MetricValue, average_equity: MetricValue) -> MetricValue:
        try:
            validate_same_statement(net_income, average_equity)
            if average_equity.value in (None, 0) or net_income.value is None:
                raise ValueError("Insufficient data")
            value = round((net_income.value / average_equity.value) * 100, 2)
            return MetricValue(
                value=value,
                unit="%",
                statement_id=net_income.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="%",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_eps(net_income: MetricValue, shares_outstanding: MetricValue) -> MetricValue:
        try:
            validate_same_statement(net_income, shares_outstanding)
            if shares_outstanding.value in (None, 0) or net_income.value is None:
                raise ValueError("Insufficient data")
            value = round(net_income.value / shares_outstanding.value, 2)
            return MetricValue(
                value=value,
                unit="INR",
                statement_id=net_income.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="INR",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_debt_to_equity(total_debt: MetricValue, total_equity: MetricValue) -> MetricValue:
        """Fundametrics Debt to Equity Ratio Calculation"""
        try:
            validate_same_statement(total_debt, total_equity)
            if total_equity.value in (None, 0) or total_debt.value is None:
                raise ValueError("Insufficient data")
            value = round(total_debt.value / total_equity.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=total_debt.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="x",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_book_value_per_share(total_equity: MetricValue, shares_outstanding: MetricValue) -> MetricValue:
        """Fundametrics Book Value Per Share Calculation"""
        try:
            validate_same_statement(total_equity, shares_outstanding)
            if shares_outstanding.value in (None, 0) or total_equity.value is None:
                raise ValueError("Insufficient data")
            value = round(total_equity.value / shares_outstanding.value, 2)
            return MetricValue(
                value=value,
                unit="INR",
                statement_id=total_equity.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="INR",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_pe_ratio(share_price: float, eps: MetricValue) -> MetricValue:
        """Fundametrics P/E Ratio Calculation"""
        try:
            if not share_price or eps.value is None or eps.value <= 0:
                raise ValueError("Insufficient data or negative EPS")
            value = round(share_price / eps.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=eps.statement_id,
                computed=True,
            )
        except ValueError as err:
            return MetricValue(
                value=None,
                unit="x",
                statement_id=None,
                computed=True,
                reason=str(err),
            )

    @staticmethod
    def calc_price_to_book(share_price: float, bvps: MetricValue) -> MetricValue:
        """Fundametrics Price to Book Ratio Calculation"""
        try:
            if not share_price or bvps.value is None or bvps.value <= 0:
                raise ValueError("Insufficient data or negative BVPS")
            value = round(share_price / bvps.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=bvps.statement_id,
                computed=True,
            )
        except ValueError as err:
            return MetricValue(
                value=None,
                unit="x",
                statement_id=None,
                computed=True,
                reason=str(err),
            )

    @staticmethod
    def calc_capital_efficiency_score(roce: MetricValue, asset_turnover: MetricValue) -> MetricValue:
        """
        Fundametrics Capital Efficiency Score
        Formula: (ROCE × Asset Turnover)
        Measures how efficiently capital and assets are used to generate returns
        """
        try:
            validate_same_statement(roce, asset_turnover)
            if roce.value is None or asset_turnover.value is None:
                raise ValueError("Insufficient data")
            value = round(roce.value * asset_turnover.value, 2)
            return MetricValue(
                value=value,
                unit="",
                statement_id=roce.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return MetricValue(
                value=None,
                unit="",
                statement_id=None,
                computed=True,
                reason=reason,
            )

    @staticmethod
    def calc_profit_stability_index(net_margins: List[MetricValue]) -> MetricValue:
        """
        Fundametrics Profit Stability Index
        Formula: 1 / standard deviation of net margin (5-year)
        Higher values indicate more stable profitability
        """
        if not net_margins or len(net_margins) < 2:
            return MetricValue(
                value=None,
                unit="",
                statement_id=None,
                computed=True,
                reason="Insufficient history",
            )

        # Filter out None values
        try:
            validate_same_statement(*net_margins)
        except MetricConsistencyError:
            return MetricValue(
                value=None,
                unit="",
                statement_id=None,
                computed=True,
                reason="Cross-statement mismatch",
            )

        valid_values = [m.value for m in net_margins if m.value is not None]
        if len(valid_values) < 2:
            return FundametricsMetricsEngine._metric_missing("", "Insufficient history")

        try:
            import statistics
            std_dev = statistics.stdev(valid_values)
            if std_dev == 0:
                raise ValueError("Zero variance")
            value = round(1 / std_dev, 2)
            return MetricValue(
                value=value,
                unit="",
                statement_id=net_margins[-1].statement_id,
                computed=True,
            )
        except Exception as err:
            return MetricValue(
                value=None,
                unit="",
                statement_id=None,
                computed=True,
                reason=str(err),
            )

    @staticmethod
    def calc_debt_safety_indicator(operating_cash_flow: MetricValue, total_debt: MetricValue) -> MetricValue:
        try:
            validate_same_statement(operating_cash_flow, total_debt)
            if total_debt.value in (None, 0) or operating_cash_flow.value is None:
                raise ValueError("Insufficient data")
            value = round(operating_cash_flow.value / total_debt.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=operating_cash_flow.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return FundametricsMetricsEngine._metric_missing("x", reason)

    @staticmethod
    def calc_earnings_quality_ratio(operating_cash_flow: MetricValue, net_profit: MetricValue) -> MetricValue:
        try:
            validate_same_statement(operating_cash_flow, net_profit)
            if net_profit.value in (None, 0) or operating_cash_flow.value is None:
                raise ValueError("Insufficient data")
            value = round(operating_cash_flow.value / net_profit.value, 2)
            return MetricValue(
                value=value,
                unit="x",
                statement_id=net_profit.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError) as err:
            reason = "Cross-statement mismatch" if isinstance(err, MetricConsistencyError) else str(err)
            return FundametricsMetricsEngine._metric_missing("x", reason)

    @staticmethod
    def calc_market_cap(share_price: float, shares_outstanding: float) -> Optional[float]:
        """Fundametrics Market Capitalization Calculation"""
        if not share_price or not shares_outstanding:
            return None
        return round(share_price * shares_outstanding, 2)

    @staticmethod
    def compute_growth_rate(start_val: float, end_val: float, periods: int) -> Optional[float]:
        """Fundametrics Annualized Growth Rate (CAGR Alternative)"""
        if start_val is None or end_val is None or start_val == 0 or periods <= 0:
            return None
        # CAGR is not defined for negative transitions
        if (end_val / start_val) <= 0:
            return None
        try:
            res = ((end_val / start_val) ** (1 / periods) - 1) * 100
            if isinstance(res, complex):
                return None
            return round(float(res.real), 2)
        except (ZeroDivisionError, ValueError, TypeError):
            return None

    def compute_fundametrics_metrics(
        self,
        *,
        income_statement: Dict[str, Dict[str, float]],
        balance_sheet: Optional[Dict[str, Dict[str, float]]] = None,
        shares_outstanding: Optional[float] = None,
        share_price: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
        metric_values = self.compute_metric_values(
            income_statement=income_statement,
            balance_sheet=balance_sheet,
            shares_outstanding=shares_outstanding,
            share_price=share_price,
        )
        return {key: metric.value for key, metric in metric_values.items()}

    def compute_metric_values(
        self,
        *,
        income_statement: Dict[str, Dict[str, Any]],
        balance_sheet: Optional[Dict[str, Dict[str, Any]]] = None,
        shares_outstanding: Optional[Any] = None,
        share_price: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, MetricValue]:
        units = {
            "fundametrics_operating_margin": "%",
            "fundametrics_net_margin": "%",
            "fundametrics_interest_coverage": "x",
            "fundametrics_return_on_equity": "%",
            "fundametrics_asset_turnover": "x",
            "fundametrics_eps": "INR",
            "fundametrics_market_cap": "INR",
            "fundametrics_pe_ratio": "x",
            "fundametrics_price_to_book": "x",
            "fundametrics_debt_to_equity": "x",
            "fundametrics_book_value_per_share": "INR",
            "fundametrics_growth_rate_internal": "%",
            "fundametrics_sales_growth_10y": "%",
            "fundametrics_sales_growth_5y": "%",
            "fundametrics_sales_growth_3y": "%",
            "fundametrics_sales_growth_1y": "%",
            "fundametrics_profit_growth_10y": "%",
            "fundametrics_profit_growth_5y": "%",
            "fundametrics_profit_growth_3y": "%",
            "fundametrics_profit_growth_1y": "%",
            "fundametrics_roe_10y": "%",
            "fundametrics_roe_5y": "%",
            "fundametrics_roe_3y": "%",
        }

        metrics: Dict[str, MetricValue] = {
            key: self._metric_missing(unit, "Not computed") for key, unit in units.items()
        }

        if not income_statement:
            return metrics

        ordered_periods = sorted(income_statement.keys(), key=self._period_sort_key)
        if not ordered_periods:
            return metrics

        latest_period = ordered_periods[-1]
        latest_row = income_statement.get(latest_period, {}) or {}
        previous_period = ordered_periods[-2] if len(ordered_periods) > 1 else None

        def coerce(row: Dict[str, Any], key: str, unit: str, reason: str) -> MetricValue:
            value = row.get(key)
            return self._coerce_metric(value, unit, reason=reason)

        revenue = coerce(latest_row, "revenue", "INR", "Revenue unavailable")
        operating_profit = coerce(latest_row, "operating_profit", "INR", "Operating profit unavailable")
        net_income = coerce(latest_row, "net_income", "INR", "Net income unavailable")
        interest = coerce(latest_row, "interest", "INR", "Interest unavailable")
        profit_before_tax = coerce(latest_row, "profit_before_tax", "INR", "Profit before tax unavailable")
        ebit = coerce(latest_row, "ebit", "INR", "EBIT unavailable")

        if ebit.value is None and profit_before_tax.value is not None and interest.value is not None:
            ebit = self._sum_metrics([profit_before_tax, interest], "INR", reason="EBIT components mismatch")

        metrics["fundametrics_operating_margin"] = self._seed_confidence(
            self.calc_operating_margin(revenue, operating_profit),
            metadata=metadata,
            inputs=[revenue, operating_profit],
        )
        metrics["fundametrics_net_margin"] = self._seed_confidence(
            self.calc_net_margin(revenue, net_income),
            metadata=metadata,
            inputs=[revenue, net_income],
        )
        metrics["fundametrics_interest_coverage"] = self._seed_confidence(
            self.calc_interest_coverage(ebit, interest),
            metadata=metadata,
            inputs=[ebit, interest],
        )

        balance_row = balance_sheet.get(latest_period)
        if balance_row is None and isinstance(balance_sheet, dict):
            # Fallback to latest available BS
            bs_periods = sorted(balance_sheet.keys(), key=self._period_sort_key)
            if bs_periods:
                balance_row = balance_sheet.get(bs_periods[-1])
        
        balance_row = balance_row or {}

        total_assets = coerce(balance_row, "total_assets", "INR", "Total assets unavailable")
        metrics["fundametrics_asset_turnover"] = self._seed_confidence(
            self.calc_asset_turnover(revenue, total_assets),
            metadata=metadata,
            inputs=[revenue, total_assets],
        )

        def extract_equity(row: Dict[str, Any]) -> MetricValue:
            for candidate in ("shareholder_equity", "total_equity", "equity"):
                metric = row.get(candidate)
                if isinstance(metric, MetricValue):
                    return metric
                if metric is not None:
                    return self._coerce_metric(metric, "INR", reason="Equity unavailable")
            components = []
            for part in ("equity_capital", "reserves"):
                metric = row.get(part)
                if isinstance(metric, MetricValue):
                    components.append(metric)
                elif metric is not None:
                    components.append(self._coerce_metric(metric, "INR", reason="Equity component unavailable"))
            if components:
                return self._sum_metrics(components, "INR", reason="Equity components mismatch")
            return self._metric_missing("INR", "Equity unavailable")

        equity_current = extract_equity(balance_row)
        balance_prev = balance_sheet.get(previous_period, {}) if previous_period and isinstance(balance_sheet, dict) else {}
        equity_previous = extract_equity(balance_prev)

        metrics["fundametrics_return_on_equity"] = self._seed_confidence(
            self._compute_return_on_equity(net_income, equity_current, equity_previous),
            metadata=metadata,
            inputs=[net_income, equity_current, equity_previous],
        )

        borrowings = coerce(balance_row, "borrowings", "INR", "Borrowings unavailable")
        metrics["fundametrics_debt_to_equity"] = self._seed_confidence(
            self.calc_debt_to_equity(borrowings, equity_current),
            metadata=metadata,
            inputs=[borrowings, equity_current],
        )

        shares = self._coerce_metric(shares_outstanding, "shares", reason="Shares unavailable")
        metrics["fundametrics_eps"] = self._seed_confidence(
            self.calc_eps(net_income, shares),
            metadata=metadata,
            inputs=[net_income, shares],
        )

        metrics["fundametrics_book_value_per_share"] = self._seed_confidence(
            self.calc_book_value_per_share(equity_current, shares),
            metadata=metadata,
            inputs=[equity_current, shares],
        )

        bvps = metrics["fundametrics_book_value_per_share"]
        curr_eps = metrics["fundametrics_eps"]

        if share_price:
            metrics["fundametrics_pe_ratio"] = self._seed_confidence(
                self.calc_pe_ratio(float(share_price), curr_eps),
                metadata=metadata,
                inputs=[curr_eps],
            )
            metrics["fundametrics_price_to_book"] = self._seed_confidence(
                self.calc_price_to_book(float(share_price), bvps),
                metadata=metadata,
                inputs=[bvps],
            )

        # --- COMPOUNDED GROWTH HORIZONS ---
        for horizon in [10, 5, 3, 1]:
            if len(ordered_periods) > horizon:
                start_p = ordered_periods[-(horizon+1)]
                end_p = ordered_periods[-1]
                
                # Sales Growth
                raw_start = income_statement.get(start_p, {}).get("revenue")
                raw_end = income_statement.get(end_p, {}).get("revenue")
                start_rev = raw_start.value if isinstance(raw_start, MetricValue) else raw_start
                end_rev = raw_end.value if isinstance(raw_end, MetricValue) else raw_end
                
                if start_rev and end_rev:
                    val = self.compute_growth_rate(start_rev, end_rev, horizon)
                    if val is not None:
                        metrics[f"fundametrics_sales_growth_{horizon}y"] = MetricValue(val, "%", None, True)
                
                # Profit Growth
                raw_start_ni = income_statement.get(start_p, {}).get("net_income")
                raw_end_ni = income_statement.get(end_p, {}).get("net_income")
                start_ni = raw_start_ni.value if isinstance(raw_start_ni, MetricValue) else raw_start_ni
                end_ni = raw_end_ni.value if isinstance(raw_end_ni, MetricValue) else raw_end_ni
                
                if start_ni and end_ni:
                    val = self.compute_growth_rate(start_ni, end_ni, horizon)
                    if val is not None:
                        metrics[f"fundametrics_profit_growth_{horizon}y"] = MetricValue(val, "%", None, True)

        # Average ROE Horizons
        for horizon in [10, 5, 3]:
            if len(ordered_periods) >= horizon:
                relevant_periods = ordered_periods[-horizon:]
                roe_values = []
                for p in relevant_periods:
                    raw_ni = income_statement.get(p, {}).get("net_income")
                    ni_val = raw_ni.value if isinstance(raw_ni, MetricValue) else raw_ni
                    bs_p = balance_sheet.get(p, {}) if isinstance(balance_sheet, dict) else {}
                    eq = extract_equity(bs_p)
                    if ni_val and eq.value:
                        roe_values.append(float(ni_val) / float(eq.value) * 100)
                
                if roe_values:
                    avg_roe = sum(roe_values) / len(roe_values)
                    metrics[f"fundametrics_roe_{horizon}y"] = MetricValue(round(avg_roe, 2), "%", None, True)

        # Overall Internal Growth Rate (Full history)
        if len(ordered_periods) > 1:
            raw_start_ni = income_statement.get(ordered_periods[0], {}).get("net_income")
            raw_end_ni = income_statement.get(ordered_periods[-1], {}).get("net_income")
            start_ni = raw_start_ni.value if isinstance(raw_start_ni, MetricValue) else raw_start_ni
            end_ni = raw_end_ni.value if isinstance(raw_end_ni, MetricValue) else raw_end_ni
            if start_ni and end_ni:
                val = self.compute_growth_rate(start_ni, end_ni, len(ordered_periods) - 1)
                if val is not None:
                    metrics["fundametrics_growth_rate_internal"] = MetricValue(val, "%", None, True)

        for key, metric in list(metrics.items()):
            if metric.confidence is None:
                metrics[key] = self._seed_confidence(metric, metadata=metadata)

        return metrics

    @staticmethod
    def _statement_scope_key(metric: MetricValue) -> Optional[str]:
        if metric.statement_id:
            parts = metric.statement_id.split("_")
            if len(parts) >= 2:
                return "_".join(parts[:2])
        return None

    def _compute_return_on_equity(
        self,
        net_income: MetricValue,
        equity_current: MetricValue,
        equity_previous: MetricValue,
    ) -> MetricValue:
        if net_income.value is None or equity_current.value is None or equity_previous.value is None:
            return self._metric_missing("%", "Insufficient equity history")

        scope_keys = {
            self._statement_scope_key(net_income),
            self._statement_scope_key(equity_current),
            self._statement_scope_key(equity_previous),
        }
        if None in scope_keys or len(scope_keys) != 1:
            return self._metric_missing("%", "Insufficient equity history")

        average_equity = (equity_current.value + equity_previous.value) / 2
        if average_equity in (None, 0):
            return self._metric_missing("%", "Insufficient equity history")

        try:
            value = round((net_income.value / average_equity) * 100, 2)
        except ZeroDivisionError:
            return self._metric_missing("%", "Insufficient equity history")

        return MetricValue(
            value=value,
            unit="%",
            statement_id=net_income.statement_id,
            computed=True,
        )

    def analyze_company_history(
        self,
        financials: Dict[str, Dict[str, float]],
        balance_sheet: Optional[Dict[str, Dict[str, float]]] = None,
        shares_outstanding: Optional[float] = None,
        share_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Processes year-keyed raw data to generate Fundametrics Metrics for historical analysis.
        Input: financials['income_statement'] = {"FY2022": {...}, "FY2023": {...}}
        """
        if not financials:
            return {}

        ordered_periods = sorted(financials.keys(), key=self._period_sort_key)

        results: Dict[str, Any] = {"annual_metrics": {}}
        for period in ordered_periods:
            period_data = financials[period]
            revenue = period_data.get('revenue')
            operating_profit = period_data.get('operating_profit')
            results["annual_metrics"][period] = {
                "fundametrics_operating_margin": self.calc_operating_margin(revenue, operating_profit) if revenue is not None and operating_profit is not None else None
            }

        if len(ordered_periods) > 1:
            first_period = ordered_periods[0]
            last_period = ordered_periods[-1]
            periods = len(ordered_periods) - 1
            results["growth_metrics"] = {
                "fundametrics_revenue_growth_annualized": self.compute_growth_rate(
                    financials[first_period].get('revenue'),
                    financials[last_period].get('revenue'),
                    periods
                ),
                "fundametrics_growth_rate_internal": self.compute_growth_rate(
                    financials[first_period].get('net_income'),
                    financials[last_period].get('net_income'),
                    periods
                )
            }

        summary_metrics = self.compute_fundametrics_metrics(
            income_statement=financials,
            balance_sheet=balance_sheet,
            shares_outstanding=shares_outstanding,
            share_price=share_price
        )
        if summary_metrics:
            results["summary_metrics"] = summary_metrics

        return results
