from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from scraper.core.metrics import MetricValue
from scraper.core.validators import MetricConsistencyError, validate_same_statement
from scraper.core.confidence import compute_confidence


class FundametricsRatiosEngine:
    """Compute Fundametrics-owned financial ratios from cleaned facts."""

    def __init__(self) -> None:
        self._now = lambda: datetime.now(timezone.utc)

    @staticmethod
    def _period_sort_key(period: str) -> int:
        """Extract year component for chronological sorting."""
        if not period:
            return 0
        if "TTM" in str(period).upper():
            return 9999
        import re
        match = re.search(r"(\d{4})", str(period))
        return int(match.group(1)) if match else 0

    @staticmethod
    def _source_from_metrics(metrics: List[MetricValue]) -> str:
        for metric in metrics:
            if metric and metric.statement_id and ("_NSE_" in metric.statement_id.upper() or "_BSE_" in metric.statement_id.upper()):
                return "exchange"
        return "derived"

    @staticmethod
    def _completeness_ratio(metrics: List[MetricValue]) -> Optional[float]:
        if not metrics:
            return None
        total = len(metrics)
        present = sum(1 for metric in metrics if metric and metric.value is not None)
        return present / total if total else None

    def _seed_confidence(
        self,
        metric: MetricValue,
        *,
        inputs: List[MetricValue],
        metadata: Optional[Dict[str, Any]],
        stability: Optional[object] = None,
    ) -> MetricValue:
        metadata = metadata or {}
        ctx: Dict[str, Any] = {
            "source_type": self._source_from_metrics(inputs + [metric]),
        }
        generated = metadata.get("generated")
        if generated is not None:
            ctx["generated_at"] = generated
        ttl_hours = metadata.get("ttl_hours")
        if ttl_hours is not None:
            ctx["ttl_hours"] = ttl_hours
        ratio = self._completeness_ratio(inputs)
        if ratio is not None:
            ctx["completeness_ratio"] = ratio
        if stability is not None:
            ctx["stability"] = stability

        status_ids = {metric.statement_id for metric in inputs + [metric] if metric and metric.statement_id}
        if not status_ids:
            ctx["statement_status"] = "partial"
        elif len(status_ids) == 1:
            ctx["statement_status"] = "matched"
        else:
            ctx["statement_status"] = "inconsistent"

        metric.confidence_inputs = ctx
        metric.confidence = compute_confidence(metric, None, self._now())
        return metric

    @staticmethod
    def _cap_confidence_downstream(metric: MetricValue, inputs: List[MetricValue]) -> MetricValue:
        confidences = [m.confidence for m in inputs + [metric] if m and m.confidence]
        if not confidences or not metric.confidence:
            return metric
        min_score = min(conf.score for conf in confidences)
        metric.confidence = metric.confidence.cap(min_score)
        return metric

    def compute(
        self,
        *,
        income_statement: Optional[Dict[str, Dict[str, Any]]],
        balance_sheet: Optional[Dict[str, Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, MetricValue]:
        ratios: Dict[str, MetricValue] = {}

        if not income_statement:
            return ratios

        periods = [period for period in income_statement.keys() if isinstance(period, str)]
        if not periods:
            return ratios

        periods.sort()
        latest_period = periods[-1]
        latest_row = income_statement.get(latest_period, {}) or {}
        prior_period = periods[-2] if len(periods) > 1 else None
        prior_row = income_statement.get(prior_period, {}) if prior_period else {}

        def coerce(row: Dict[str, Any], key: str, unit: str, reason: str) -> MetricValue:
            value = row.get(key)
            if isinstance(value, MetricValue):
                return value
            if value is None:
                return self._metric_missing(unit, reason)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return self._metric_missing(unit, reason)
            return MetricValue(
                value=numeric,
                unit=unit,
                statement_id=None,
                computed=False,
            )

        meta = metadata or {}

        revenue = coerce(latest_row, "revenue", "INR", "Revenue unavailable")
        operating_profit = coerce(latest_row, "operating_profit", "INR", "Operating profit unavailable")
        net_income = coerce(latest_row, "net_income", "INR", "Net income unavailable")
        interest = coerce(latest_row, "interest", "INR", "Interest unavailable")
        profit_before_tax = coerce(latest_row, "profit_before_tax", "INR", "Profit before tax unavailable")

        ebit = coerce(latest_row, "ebit", "INR", "EBIT unavailable")
        
        # Use Operating Profit as strong proxy for EBIT if explicit EBIT is missing
        if ebit.value is None and operating_profit.value is not None:
            ebit = operating_profit  
        elif ebit.value is None and profit_before_tax.value is not None and interest.value is not None:
            ebit = self._sum_metrics([profit_before_tax, interest], "INR", "EBIT components mismatch")

        equity_current = self._resolve_equity_metric(balance_sheet, latest_period)
        equity_previous = self._resolve_equity_metric(balance_sheet, prior_period)
        capital_employed = self._resolve_capital_employed_metric(balance_sheet, latest_period, equity_current)
        shares_outstanding = self._resolve_shares_outstanding_metric(balance_sheet, meta)
        share_price_metric = self._resolve_share_price_metric(meta)
        total_debt = self._resolve_total_debt_metric(balance_sheet, latest_period)

        def build_ratio(
            key: str,
            numerator: MetricValue,
            denominator: MetricValue,
            unit: str,
            reason: str,
            *,
            extra_inputs: Optional[List[MetricValue]] = None,
        ) -> MetricValue:
            inputs = [numerator, denominator] + (extra_inputs or [])
            base = self._derive_ratio(numerator, denominator, unit, reason)
            seeded = self._seed_confidence(base, inputs=inputs, metadata=meta)
            capped = self._cap_confidence_downstream(seeded, inputs)
            ratios[key] = capped
            return capped

        build_ratio(
            "operating_margin",
            operating_profit,
            revenue,
            "%",
            "Operating margin unavailable",
        )
        build_ratio(
            "net_profit_margin",
            net_income,
            revenue,
            "%",
            "Net margin unavailable",
        )

        roe_metric = self._compute_roe(net_income, equity_current, equity_previous)
        ratios["return_on_equity"] = self._cap_confidence_downstream(
            self._seed_confidence(
                roe_metric,
                inputs=[net_income, equity_current, equity_previous],
                metadata=meta,
            ),
            [net_income, equity_current, equity_previous],
        )

        build_ratio(
            "return_on_capital_employed",
            ebit,
            capital_employed,
            "%",
            "ROCE unavailable",
        )

        eps_metric = build_ratio(
            "earnings_per_share",
            net_income,
            shares_outstanding,
            "INR",
            "EPS unavailable",
        )

        share_price_metric = self._seed_confidence(share_price_metric, inputs=[], metadata=meta)

        build_ratio(
            "price_to_earnings",
            share_price_metric,
            eps_metric,
            "x",
            "P/E unavailable",
        )

        book_value_metric = build_ratio(
            "book_value_per_share",
            equity_current,
            shares_outstanding,
            "INR",
            "Book value per share unavailable",
        )

        build_ratio(
            "price_to_book",
            share_price_metric,
            book_value_metric,
            "x",
            "P/B unavailable",
            extra_inputs=[equity_current, shares_outstanding],
        )

        build_ratio(
            "debt_to_equity",
            total_debt,
            equity_current,
            "x",
            "Debt to equity unavailable",
        )

        build_ratio(
            "interest_coverage",
            ebit,
            interest,
            "x",
            "Interest coverage unavailable",
        )

        return ratios

    # ------------------------------------------------------------------
    @staticmethod
    def _metric_missing(unit: str, reason: str) -> MetricValue:
        return MetricValue(
            value=None,
            unit=unit,
            statement_id=None,
            computed=True,
            reason=reason,
        )

    def _derive_ratio(
        self,
        numerator: MetricValue,
        denominator: MetricValue,
        unit: str,
        reason: str,
    ) -> MetricValue:
        try:
            validate_same_statement(numerator, denominator)
            if numerator.value is None or denominator.value in (None, 0):
                raise ValueError(reason)
            value = numerator.value / denominator.value
            if unit == "%":
                value = round(value * 100, 2)
            else:
                value = round(value, 4)
            return MetricValue(
                value=value,
                unit=unit,
                statement_id=numerator.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError):
            return self._metric_missing(unit, reason)

    def _sum_metrics(self, metrics: List[MetricValue], unit: str, reason: str) -> MetricValue:
        base: Optional[MetricValue] = None
        total = 0.0
        try:
            for metric in metrics:
                if metric.value is None:
                    raise ValueError(reason)
                if base is None:
                    base = metric
                else:
                    validate_same_statement(base, metric)
                total += metric.value
            if base is None:
                raise ValueError(reason)
            return MetricValue(
                value=round(total, 2),
                unit=unit,
                statement_id=base.statement_id,
                computed=True,
            )
        except (MetricConsistencyError, ValueError):
            return self._metric_missing(unit, reason)

    def _resolve_equity_metric(
        self,
        balance_sheet: Optional[Dict[str, Dict[str, Any]]],
        period: Optional[str],
    ) -> MetricValue:
        if not balance_sheet:
            return self._metric_missing("INR", "Equity unavailable")
        
        row = balance_sheet.get(period)
        if not row:
            # Fallback for TTM/mismatched periods: Use latest available BS period
            try:
                latest_p = sorted(balance_sheet.keys(), key=self._period_sort_key)[-1]
                row = balance_sheet.get(latest_p, {})
            except (ValueError, IndexError):
                return self._metric_missing("INR", "Equity unavailable")

        for key in ("shareholder_equity", "total_equity", "equity"):
            value = row.get(key)
            if isinstance(value, MetricValue):
                return value
            if value is not None:
                return self._derive_metric_value(value, "INR")
        components = []
        for part in ("equity_capital", "reserves"):
            value = row.get(part)
            if isinstance(value, MetricValue):
                components.append(value)
            elif value is not None:
                components.append(self._derive_metric_value(value, "INR"))
        if components:
            return self._sum_metrics(components, "INR", "Equity components mismatch")
        return self._metric_missing("INR", "Equity unavailable")

    def _derive_metric_value(self, raw: Any, unit: str) -> MetricValue:
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return self._metric_missing(unit, "Metric unavailable")
        return MetricValue(
            value=numeric,
            unit=unit,
            statement_id=None,
            computed=False,
        )

    def _resolve_total_debt_metric(
        self,
        balance_sheet: Optional[Dict[str, Dict[str, Any]]],
        period: Optional[str],
    ) -> MetricValue:
        if not balance_sheet:
            return self._metric_missing("INR", "Total debt unavailable")
            
        latest = balance_sheet.get(period)
        if not latest:
            # Fallback to latest available BS period
            try:
                latest_p = sorted(balance_sheet.keys(), key=self._period_sort_key)[-1]
                latest = balance_sheet.get(latest_p, {})
            except (ValueError, IndexError):
                return self._metric_missing("INR", "Total debt unavailable")

        for key in ("total_debt", "borrowings", "long_term_borrowings", "debt"):
            value = latest.get(key)
            if isinstance(value, MetricValue):
                return value
            if value is not None:
                return self._derive_metric_value(value, "INR")
        return self._metric_missing("INR", "Total debt unavailable")

    def _resolve_capital_employed_metric(
        self,
        balance_sheet: Optional[Dict[str, Dict[str, Any]]],
        period: str,
        equity: MetricValue,
    ) -> MetricValue:
        if not balance_sheet:
            return self._metric_missing("INR", "Capital employed unavailable")
        row = balance_sheet.get(period, {}) or {}
        direct = row.get("capital_employed")
        if isinstance(direct, MetricValue):
            return direct
        if direct is not None:
            return self._derive_metric_value(direct, "INR")

        total_assets = row.get("total_assets")
        if isinstance(total_assets, MetricValue):
            assets_metric = total_assets
        elif total_assets is not None:
            assets_metric = self._derive_metric_value(total_assets, "INR")
        else:
            assets_metric = self._metric_missing("INR", "Total assets unavailable")

        total_debt = self._resolve_total_debt_metric(balance_sheet, period)
        candidates = [metric for metric in (equity, total_debt) if metric.value is not None]
        if len(candidates) == 2:
            return self._sum_metrics(candidates, "INR", "Capital employed mismatch")

        if assets_metric.value is not None and total_debt.value is not None:
            return self._sum_metrics([assets_metric, total_debt], "INR", "Capital employed mismatch")

        return self._metric_missing("INR", "Capital employed unavailable")

    def _resolve_shares_outstanding_metric(
        self,
        balance_sheet: Optional[Dict[str, Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]],
    ) -> MetricValue:
        if metadata:
            direct = metadata.get("shares_outstanding")
            if isinstance(direct, MetricValue):
                return direct
            if direct is not None:
                return self._derive_metric_value(direct, "shares")
            constants = metadata.get("constants") if isinstance(metadata.get("constants"), dict) else {}
            direct = constants.get("shares_outstanding") if constants else None
            if direct is not None:
                return self._derive_metric_value(direct, "shares")

        if not balance_sheet:
            return self._metric_missing("shares", "Shares outstanding unavailable")

        latest_period = max(balance_sheet.keys())
        latest = balance_sheet.get(latest_period, {}) or {}
        equity_capital = latest.get("equity_capital")
        constants = metadata.get("constants") if metadata and isinstance(metadata.get("constants"), dict) else {}
        face_value = constants.get("face_value") if constants else None

        if equity_capital is not None and face_value not in (None, 0):
            try:
                shares = float(equity_capital) / float(face_value)
                return MetricValue(
                    value=shares,
                    unit="shares",
                    statement_id=None,
                    computed=True,
                )
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        return self._metric_missing("shares", "Shares outstanding unavailable")

    def _resolve_share_price_metric(self, metadata: Optional[Dict[str, Any]]) -> MetricValue:
        if not metadata:
            return self._metric_missing("INR", "Share price unavailable")
        direct = metadata.get("share_price")
        if isinstance(direct, MetricValue):
            return direct
        if direct is not None:
            return self._derive_metric_value(direct, "INR")
        constants = metadata.get("constants") if isinstance(metadata.get("constants"), dict) else {}
        direct = constants.get("share_price") if constants else None
        if direct is not None:
            return self._derive_metric_value(direct, "INR")
        return self._metric_missing("INR", "Share price unavailable")

    def _compute_roe(
        self,
        net_income: MetricValue,
        equity_current: MetricValue,
        equity_previous: MetricValue,
    ) -> MetricValue:
        if (
            net_income.value is None
            or equity_current.value is None
            or equity_previous.value is None
        ):
            return self._metric_missing("%", "Insufficient equity history")

        scope_keys = {
            self._scope_token(net_income.statement_id),
            self._scope_token(equity_current.statement_id),
            self._scope_token(equity_previous.statement_id),
        }
        if None in scope_keys or len(scope_keys) != 1:
            return self._metric_missing("%", "Insufficient equity history")

        average_equity = (equity_current.value + equity_previous.value) / 2
        if average_equity in (None, 0):
            return self._metric_missing("%", "Insufficient equity history")

        try:
            value = round((net_income.value / average_equity) * 100, 4)
        except ZeroDivisionError:
            return self._metric_missing("%", "Insufficient equity history")

        return MetricValue(
            value=value,
            unit="%",
            statement_id=net_income.statement_id,
            computed=True,
        )

    @staticmethod
    def _scope_token(statement_id: Optional[str]) -> Optional[str]:
        if not statement_id:
            return None
        parts = statement_id.split("_")
        if len(parts) < 2:
            return None
        return "_".join(parts[:2])
