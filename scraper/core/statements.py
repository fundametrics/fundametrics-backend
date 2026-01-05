"""Canonical financial statement models for Fundametrics ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, Literal, Optional

_MONTH_MAP = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

StatementFrequency = Literal["annual", "quarterly"]
StatementScope = Literal["standalone", "consolidated"]
StatementExchange = Literal["NSE", "BSE"]


@dataclass(frozen=True)
class FinancialStatement:
    statement_id: str
    period_start: date
    period_end: date
    frequency: StatementFrequency
    scope: StatementScope
    exchange: StatementExchange
    currency: str = "INR"


__all__ = [
    "build_financial_statement",
    "statement_to_dict",
    "FinancialStatement",
    "StatementFrequency",
    "StatementScope",
    "StatementExchange",
]


def _infer_frequency(period: str) -> Optional[StatementFrequency]:
    token = period.strip().lower()
    if token.startswith("q") or "quarter" in token:
        return "quarterly"
    if token.startswith("ttm"):
        return None
    return "annual"


def _resolve_month(token: str) -> Optional[int]:
    cleaned = token.strip().lower()
    return _MONTH_MAP.get(cleaned[:3])


def _infer_period_end(period: str) -> Optional[date]:
    token = period.strip()
    if not token:
        return None

    parts = token.replace("/", " ").replace("-", " ").split()
    year = None
    month = None

    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = int(part)
        elif part.upper().startswith("FY") and len(part) in {4, 5}:
            suffix = part[2:]
            if suffix.isdigit():
                year = 2000 + int(suffix)
        else:
            resolved = _resolve_month(part)
            if resolved:
                month = resolved

    if year is None:
        return None

    if month is None:
        # Assume March year-end for annual financial statements
        month = 3
    if month == 3:
        day = 31
    elif month in {1, 5, 7, 8, 10, 12}:
        day = 31
    elif month == 2:
        day = 29 if year % 4 == 0 else 28
    else:
        day = 30

    return date(year, month, day)


def _infer_period_start(frequency: StatementFrequency, period_end: date) -> date:
    if frequency == "annual":
        # Assume 1-year periods; Indian corporates usually April-March
        if period_end.month == 3:
            return date(period_end.year - 1, 4, 1)
        return date(period_end.year - 1, period_end.month + 1 if period_end.month < 12 else 1, 1)

    # Quarterly assumption: quarter spans 3 months ending on period_end
    month = period_end.month - 2
    year = period_end.year
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def build_financial_statement(
    *,
    period: str,
    scope: StatementScope,
    exchange: StatementExchange,
    frequency: Optional[StatementFrequency] = None,
    currency: str = "INR",
    statement_type: str = "income",
) -> Optional[FinancialStatement]:
    inferred_frequency = frequency or _infer_frequency(period)
    if inferred_frequency is None:
        return None

    period_end = _infer_period_end(period)
    if period_end is None:
        return None

    period_start = _infer_period_start(inferred_frequency, period_end)
    if scope is None or exchange is None:
        return None

    scope_token = scope.upper()
    exchange_token = exchange.upper()
    statement_id = f"{scope_token}_{exchange_token}_{inferred_frequency.upper()}_{period_end.isoformat()}"

    return FinancialStatement(
        statement_id=statement_id,
        period_start=period_start,
        period_end=period_end,
        frequency=inferred_frequency,
        scope=scope,
        exchange=exchange,
        currency=currency,
    )


def statement_to_dict(statement: FinancialStatement) -> Dict[str, str]:
    payload = asdict(statement)
    payload["period_start"] = statement.period_start.isoformat()
    payload["period_end"] = statement.period_end.isoformat()
    return payload


def clone_statement_with_type(statement: FinancialStatement, statement_type: str) -> FinancialStatement:
    return FinancialStatement(
        statement_id=f"{statement.statement_id}:{statement_type.upper()}",
        period_start=statement.period_start,
        period_end=statement.period_end,
        frequency=statement.frequency,
        scope=statement.scope,
        exchange=statement.exchange,
        currency=statement.currency,
    )
