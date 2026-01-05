"""Helpers to convert cleaned financial tables into canonical Fundametrics structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from scraper.core.metrics import MetricValue
from scraper.core.statements import (
    FinancialStatement,
    StatementExchange,
    StatementFrequency,
    StatementScope,
    build_financial_statement,
)

DEFAULT_UNIT = "INR"


@dataclass
class StatementMetrics:
    statement: FinancialStatement
    metrics: Dict[str, MetricValue]


@dataclass
class FinancialTableBundle:
    statements: Dict[str, FinancialStatement]
    income_statement: Dict[str, Dict[str, MetricValue]]
    balance_sheet: Dict[str, Dict[str, MetricValue]]
    cash_flow: Dict[str, Dict[str, MetricValue]]
    ratios: Dict[str, Dict[str, MetricValue]]
    meta: Dict[str, Any]


def _wrap_metric(
    value: Optional[float],
    *,
    unit: str,
    statement_id: Optional[str],
    computed: bool = False,
    reason: Optional[str] = None,
) -> MetricValue:
    numeric_value: Optional[float]
    if isinstance(value, (int, float)):
        numeric_value = float(value)
    else:
        numeric_value = None
        if reason is None and value is not None:
            reason = "Non-numeric input"
    return MetricValue(
        value=numeric_value,
        unit=unit,
        statement_id=statement_id,
        computed=computed,
        reason=reason,
    )


def _map_table(
    table: Dict[str, Dict[str, float]],
    *,
    scope: Optional[StatementScope],
    exchange: Optional[StatementExchange],
    statement_type: str,
    currency: str,
    default_frequency: StatementFrequency = "annual",
) -> Tuple[Dict[str, FinancialStatement], Dict[str, Dict[str, MetricValue]]]:
    statements: Dict[str, FinancialStatement] = {}
    mapped: Dict[str, Dict[str, MetricValue]] = {}

    for period, row in table.items():
        statement: Optional[FinancialStatement] = None
        if scope and exchange:
            statement = build_financial_statement(
                period=period,
                scope=scope,
                exchange=exchange,
                currency=currency,
                statement_type=statement_type,
            )
        statement_id: Optional[str] = None
        if statement is not None:
            statements[statement.statement_id] = statement
            statement_id = statement.statement_id
        mapped[period] = {
            metric_key: _wrap_metric(
                metric_value,
                unit=DEFAULT_UNIT if statement_type != "cash" else currency,
                statement_id=statement_id,
            )
            for metric_key, metric_value in row.items()
        }
    return statements, mapped


def map_financial_tables(
    financials: Dict[str, Dict[str, Dict[str, float]]],
    *,
    scope: Optional[StatementScope],
    exchange: Optional[StatementExchange],
    currency: str = DEFAULT_UNIT,
) -> FinancialTableBundle:
    income = financials.get("income_statement") or {}
    balance = financials.get("balance_sheet") or {}
    cash = financials.get("cash_flow") or {}
    ratios_raw = financials.get("ratios") or {}

    statements: Dict[str, FinancialStatement] = {}

    income_statements, mapped_income = _map_table(
        income,
        scope=scope,
        exchange=exchange,
        statement_type="income",
        currency=currency,
    )
    balance_statements, mapped_balance = _map_table(
        balance,
        scope=scope,
        exchange=exchange,
        statement_type="balance",
        currency=currency,
    )
    cash_statements, mapped_cash = _map_table(
        cash,
        scope=scope,
        exchange=exchange,
        statement_type="cash",
        currency=currency,
    )
    ratio_statements, mapped_ratios = _map_table(
        ratios_raw,
        scope=scope,
        exchange=exchange,
        statement_type="ratios",
        currency="ratio",
    )

    statements.update(income_statements)
    statements.update(balance_statements)
    statements.update(cash_statements)
    statements.update(ratio_statements)

    income_periods = sorted(mapped_income.keys())
    quarterly_periods = sorted((financials.get("quarters") or {}).keys())

    return FinancialTableBundle(
        statements=statements,
        income_statement=mapped_income,
        balance_sheet=mapped_balance,
        cash_flow=mapped_cash,
        ratios=mapped_ratios,
        meta={
            "scope": scope or "unknown",
            "exchange": exchange or "unknown",
            "currency": currency,
            "periods": {
                "income": income_periods,
                "quarters": quarterly_periods,
            },
        },
    )


__all__ = ["FinancialTableBundle", "StatementMetrics", "map_financial_tables"]
