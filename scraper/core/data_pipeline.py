"""Fundametrics Data Pipeline
=======================

Centralised cleaning and validation layer that prepares raw scraped
facts before any analytics are computed.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from scraper.core.financial_mapper import map_financial_tables
from scraper.core.statements import StatementExchange, StatementScope


_EMPTY_MARKERS = {"", "-", "--", "na", "n/a", "null", "none"}
_CURRENCY_SYMBOLS = {"₹", "$", "€", "£"}


@dataclass
class ValidationIssue:
    level: str  # "warning" or "error"
    code: str
    message: str
    context: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.context:
            payload["context"] = self.context
        return payload


class DataPipeline:
    """Run end-to-end cleaning and validation for scraped payloads."""

    REQUIRED_INCOME_FIELDS = {"revenue", "operating_profit", "net_income"}
    EQUITY_KEYS = ("equity", "total_equity", "equity_capital", "share_capital")

    def process(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return cleaned data together with a validation report."""

        clean_data = self._clean(copy.deepcopy(raw_data))
        self._attach_canonical_financials(clean_data)
        issues = self._validate(clean_data, raw_data)

        status = "pass"
        if any(issue.level == "error" for issue in issues):
            status = "fail"
        elif issues:
            status = "warn"

        report = {
            "status": status,
            "issues": [issue.as_dict() for issue in issues],
        }

        return {
            "clean_data": clean_data,
            "validation_report": report,
        }

    # ------------------------------------------------------------------
    # Cleaning helpers
    # ------------------------------------------------------------------
    def _clean(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: self._clean(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._clean(item) for item in data]
        return self._normalize_scalar(data)

    def _attach_canonical_financials(self, clean_data: Dict[str, Any]) -> None:
        financials = clean_data.get("financials")
        if not isinstance(financials, dict) or not financials:
            return

        scope = clean_data.get("metadata", {}).get("scope") or "standalone"
        exchange = clean_data.get("metadata", {}).get("exchange") or "NSE"

        try:
            bundle = map_financial_tables(
                financials,
                scope=scope if scope in ("standalone", "consolidated") else "standalone",
                exchange=exchange if exchange in ("NSE", "BSE") else "NSE",
                currency=clean_data.get("metadata", {}).get("currency", "INR"),
            )
        except Exception:
            return

        clean_data.setdefault("canonical_financials", {})
        canonical = clean_data["canonical_financials"]
        canonical["statements"] = {
            key: {
                "statement_id": statement.statement_id,
                "period_start": statement.period_start.isoformat(),
                "period_end": statement.period_end.isoformat(),
                "frequency": statement.frequency,
                "scope": statement.scope,
                "exchange": statement.exchange,
                "currency": statement.currency,
            }
            for key, statement in bundle.statements.items()
        }
        canonical["income_statement"] = {
            period: {metric: value for metric, value in metrics.items()}
            for period, metrics in bundle.income_statement.items()
        }
        canonical["balance_sheet"] = {
            period: {metric: value for metric, value in metrics.items()}
            for period, metrics in bundle.balance_sheet.items()
        }
        canonical["cash_flow"] = {
            period: {metric: value for metric, value in metrics.items()}
            for period, metrics in bundle.cash_flow.items()
        }
        canonical["ratios"] = {
            period: {metric: value for metric, value in metrics.items()}
            for period, metrics in bundle.ratios.items()
        }
        canonical["meta"] = bundle.meta

    def _normalize_scalar(self, value: Any) -> Any:
        """Normalize scalars into canonical Python values."""

        if value is None:
            return None

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, bool):
            return value

        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if stripped.lower() in _EMPTY_MARKERS:
            return None

        cleaned = stripped
        # Remove currency symbols
        for symbol in _CURRENCY_SYMBOLS:
            cleaned = cleaned.replace(symbol, "")

        # Remove commas and percentage signs but track if it was a percent
        is_percent = "%" in cleaned
        cleaned = cleaned.replace("%", "")
        cleaned = cleaned.replace(",", "")

        # Handle crores notation (Cr or Cr.)
        multiplier = 1.0
        crore_match = re.search(r"\bcr(?:\.)?\b", cleaned, re.IGNORECASE)
        if crore_match:
            multiplier = 1.0  # values from screener are already in crores
            cleaned = re.sub(r"\bcr(?:\.)?\b", "", cleaned, flags=re.IGNORECASE).strip()

        # Handle parentheses signifying negative numbers
        is_negative = cleaned.startswith("(") and cleaned.endswith(")")
        if is_negative:
            cleaned = cleaned[1:-1]

        # Attempt numeric conversion
        try:
            if cleaned.count(".") == 1:
                numeric = float(cleaned)
            else:
                numeric = float(int(cleaned))

            numeric *= multiplier
            if is_percent:
                numeric = round(numeric, 4)
            if is_negative:
                numeric *= -1
            return numeric
        except ValueError:
            return stripped

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate(self, clean_data: Dict[str, Any], raw_data: Dict[str, Any]) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []

        # Attach metadata defaults
        metadata = clean_data.setdefault("metadata", {})
        metadata.setdefault("currency", "INR")
        metadata.setdefault("unit", "absolute")

        financials = clean_data.get("financials") or {}

        # Required sections
        if not financials:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="FINANCIALS_MISSING",
                    message="Financial statements not present in scraped payload.",
                )
            )
            return issues

        income_stmt = financials.get("income_statement") or {}
        if not income_stmt:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="INCOME_STATEMENT_MISSING",
                    message="Income statement data not found after cleaning.",
                )
            )
        else:
            self._validate_income_statement(income_stmt, issues)

        balance_sheet = financials.get("balance_sheet") or {}
        if balance_sheet:
            self._validate_balance_sheet(balance_sheet, issues)

        return issues

    def _validate_income_statement(self, income_stmt: Dict[str, Dict[str, Any]], issues: List[ValidationIssue]) -> None:
        periods = sorted(income_stmt.keys())
        if not periods:
            return

        latest_period = periods[-1]
        latest_row = income_stmt.get(latest_period, {})

        missing = [field for field in self.REQUIRED_INCOME_FIELDS if latest_row.get(field) in (None, "")]
        if missing:
            issues.append(
                ValidationIssue(
                    level="error",
                    code="MISSING_REQUIRED_FIELDS",
                    message=f"Latest period {latest_period} missing required fields: {', '.join(missing)}.",
                )
            )

        for period, row in income_stmt.items():
            revenue = row.get("revenue")
            if isinstance(revenue, (int, float)) and revenue < 0:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        code="NEGATIVE_REVENUE",
                        message="Negative revenue detected.",
                        context={"period": period, "value": revenue},
                    )
                )

    def _validate_balance_sheet(self, balance_sheet: Dict[str, Dict[str, Any]], issues: List[ValidationIssue]) -> None:
        periods = sorted(balance_sheet.keys())
        if not periods:
            return

        latest_period = periods[-1]
        latest_row = balance_sheet.get(latest_period, {})

        has_equity = any(latest_row.get(key) not in (None, "") for key in self.EQUITY_KEYS)
        if not has_equity:
            issues.append(
                ValidationIssue(
                    level="warning",
                    code="EQUITY_DATA_MISSING",
                    message="No equity information available in latest balance sheet period.",
                    context={"period": latest_period},
                )
            )
