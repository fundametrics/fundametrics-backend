"""Core validation helpers for Fundametrics ingestion workflows."""

from __future__ import annotations

import re
from typing import Iterable, Set

from scraper.core.metrics import MetricValue


DEFAULT_SYMBOL_ALLOWLIST: Set[str] = {
    # Initial NSE/BSE development allow-list. Extend via config or env overrides.
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "BHEL",
    "TATASTEEL",
    "HINDUNILVR",
    "MRF",
}


class SymbolValidationError(ValueError):
    """Raised when an input symbol fails validation."""


class MetricConsistencyError(ValueError):
    """Raised when metrics reference mismatched financial statements."""


def _normalise_allowlist(symbols: Iterable[str] | None) -> Set[str]:
    if not symbols:
        return set()
    normalised = {symbol.upper().strip() for symbol in symbols if symbol and symbol.strip()}
    return {symbol for symbol in normalised if re.fullmatch(r"[A-Z0-9]{2,15}", symbol)}


def validate_symbol(symbol: str, *, allowlist: Iterable[str] | None = None) -> str:
    if symbol is None:
        raise SymbolValidationError("Symbol is required")

    cleaned = symbol.upper().strip()

    if not re.fullmatch(r"[A-Z0-9]{2,15}", cleaned):
        raise SymbolValidationError("Invalid symbol format. Expected 2-15 alphanumeric characters.")

    # Allow ALL valid NSE symbols (no permission check)
    return cleaned



def validate_same_statement(*metrics: MetricValue) -> None:
    ids = {
        metric.statement_id
        for metric in metrics
        if metric is not None and metric.statement_id is not None
    }
    if len(ids) > 1:
        raise MetricConsistencyError(sorted(ids))


__all__ = [
    "validate_symbol",
    "validate_same_statement",
    "SymbolValidationError",
    "MetricConsistencyError",
    "DEFAULT_SYMBOL_ALLOWLIST",
]
