"""Normalisation helpers for symbol discovery."""

from __future__ import annotations

import re
from typing import Dict

_normalise_re = re.compile(r"[^A-Z0-9]")

_EXCHANGE_ALIASES: Dict[str, str] = {
    "NSE": "NSE",
    "NSEI": "NSE",
    "BSE": "BSE",
    "BOMBAY": "BSE",
    "NYSE": "NYSE",
    "NASDAQ": "NASDAQ",
}

_SUFFIXES = ("-EQ", "-BE", ".NS", ".BO", "EQ", "-BL", "-BZ")


def normalise_exchange(raw: str | None) -> str:
    if not raw:
        return "NSE"
    token = re.sub(r"[^A-Z]", "", raw.upper())
    return _EXCHANGE_ALIASES.get(token, token or "NSE")


def normalise_symbol(raw: str) -> str:
    if raw is None:
        raise ValueError("Symbol value is required")
    candidate = raw.strip().upper()
    for suffix in _SUFFIXES:
        if candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break
    candidate = candidate.replace(" ", "")
    candidate = _normalise_re.sub("", candidate)
    if not candidate:
        raise ValueError(f"Unable to normalise symbol: {raw}")
    return candidate


def build_symbol_key(symbol: str, exchange: str | None = None) -> str:
    normalised_symbol = normalise_symbol(symbol)
    normalised_exchange = normalise_exchange(exchange)
    return f"{normalised_symbol}:{normalised_exchange}"


__all__ = ["normalise_symbol", "normalise_exchange", "build_symbol_key"]
