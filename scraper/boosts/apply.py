"""Utilities to apply priority boosts onto the symbol registry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

from models.boost import PriorityBoost
from models.symbol import (
    MAX_TOTAL_BOOST_WEIGHT,
    SYMBOL_REGISTRY_PATH,
    SymbolRecord,
    load_symbol_registry,
    save_symbol_registry,
)

BOOST_WEIGHT_CAP = MAX_TOTAL_BOOST_WEIGHT
BOOST_TTL_CAP_HOURS = 48


class BoostError(Exception):
    """Base class for boost application errors."""


class SymbolNotFoundError(BoostError):
    """Raised when attempting to apply a boost on a missing symbol."""


class InvalidBoostRequest(BoostError):
    """Raised when a boost request fails validation."""


def _validate_weight(weight: int) -> int:
    if weight <= 0:
        raise InvalidBoostRequest("weight must be positive")
    return min(weight, BOOST_WEIGHT_CAP)


def _validate_ttl_hours(ttl_hours: int) -> int:
    if ttl_hours <= 0:
        raise InvalidBoostRequest("ttl_hours must be positive")
    return min(ttl_hours, BOOST_TTL_CAP_HOURS)


def apply_priority_boost(
    symbol: str,
    *,
    kind: str,
    weight: int,
    ttl_hours: int,
    source: str,
    registry_path=SYMBOL_REGISTRY_PATH,
) -> Tuple[SymbolRecord, PriorityBoost]:
    registry: Dict[str, SymbolRecord] = load_symbol_registry(registry_path)
    key = symbol.upper()
    if key not in registry:
        raise SymbolNotFoundError(f"Symbol {symbol} not present in registry")

    weight = _validate_weight(weight)
    ttl_hours = _validate_ttl_hours(ttl_hours)

    record = registry[key]
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=ttl_hours)

    boost = PriorityBoost(kind=kind, weight=weight, expires_at=expires_at, source=source)
    record.add_boost(boost, now=now)

    registry[key] = record
    save_symbol_registry(registry, registry_path)

    return record, boost


def prune_expired_boosts(registry: Dict[str, SymbolRecord]) -> bool:
    updated = False
    now = datetime.now(timezone.utc)
    for record in registry.values():
        if record.prune_expired_boosts(now=now):
            updated = True
    return updated


__all__ = [
    "apply_priority_boost",
    "prune_expired_boosts",
    "BOOST_WEIGHT_CAP",
    "BOOST_TTL_CAP_HOURS",
    "BoostError",
    "SymbolNotFoundError",
    "InvalidBoostRequest",
]
