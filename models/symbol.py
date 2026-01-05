"""Domain model and persistence helpers for Fundametrics symbol registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

import json

from models.boost import PriorityBoost

SYMBOL_REGISTRY_PATH = Path("data/system/symbol_registry.json")
_SYMBOL_STATUSES = {"active", "suspended", "delisted"}
_PRIORITY_LABELS = {5: "HIGH", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "LOW"}
MAX_TOTAL_BOOST_WEIGHT = 3


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class SymbolRecord:
    """Snapshot of a discoverable symbol."""

    symbol: str
    exchange: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    priority: int = 1
    status: str = "active"
    last_seen: Optional[str] = None
    last_refreshed: Optional[str] = None
    last_attempt: Optional[str] = None
    failure_count: int = 0
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    boosts: List[PriorityBoost] = field(default_factory=list)

    def __post_init__(self) -> None:  # noqa: D401
        self.symbol = self.symbol.upper().strip()
        self.exchange = self.exchange.upper().strip()
        if self.status not in _SYMBOL_STATUSES:
            self.status = "active"
        self.priority = max(1, min(int(self.priority), 5))
        # Normalise boosts list to PriorityBoost instances
        normalised_boosts: List[PriorityBoost] = []
        for boost in self.boosts:
            if isinstance(boost, PriorityBoost):
                normalised_boosts.append(boost)
                continue
            if isinstance(boost, Mapping):
                try:
                    normalised_boosts.append(PriorityBoost.from_dict(boost))
                except ValueError:
                    continue
        self.boosts = normalised_boosts

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "company_name": self.company_name,
            "sector": self.sector,
            "market_cap": self.market_cap,
            "priority": self.priority,
            "status": self.status,
            "last_seen": self.last_seen,
            "last_refreshed": self.last_refreshed,
            "last_attempt": self.last_attempt,
            "failure_count": self.failure_count,
            "source": self.source,
            "metadata": self.metadata,
            "boosts": [boost.to_dict() for boost in self.boosts],
        }
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SymbolRecord":
        return cls(
            symbol=str(payload.get("symbol", "")).upper(),
            exchange=str(payload.get("exchange", "NSE")),
            company_name=payload.get("company_name"),
            sector=payload.get("sector"),
            market_cap=payload.get("market_cap"),
            priority=int(payload.get("priority", 1) or 1),
            status=str(payload.get("status", "active")),
            last_seen=payload.get("last_seen"),
            last_refreshed=payload.get("last_refreshed"),
            last_attempt=payload.get("last_attempt"),
            failure_count=int(payload.get("failure_count", 0) or 0),
            source=payload.get("source"),
            metadata=dict(payload.get("metadata", {})),
            boosts=_load_boosts(payload.get("boosts", [])),
        )

    def touch_seen(self, *, timestamp: Optional[str] = None) -> None:
        self.last_seen = timestamp or _utc_now_iso()

    def touch_refreshed(self, *, timestamp: Optional[str] = None) -> None:
        self.last_refreshed = timestamp or _utc_now_iso()

    def mark_attempt(self, *, timestamp: Optional[str] = None) -> None:
        self.last_attempt = timestamp or _utc_now_iso()

    def record_success(self, *, timestamp: Optional[str] = None) -> None:
        ts = timestamp or _utc_now_iso()
        self.failure_count = 0
        self.last_attempt = ts
        self.touch_refreshed(timestamp=ts)

    def record_failure(self, *, timestamp: Optional[str] = None) -> None:
        self.failure_count = max(self.failure_count, 0) + 1
        self.last_attempt = timestamp or _utc_now_iso()

    def prune_expired_boosts(self, *, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        active = [boost for boost in self.boosts if boost.is_active(now)]
        changed = len(active) != len(self.boosts)
        self.boosts = active
        return changed

    def active_boosts(self, *, now: Optional[datetime] = None) -> List[PriorityBoost]:
        now = now or datetime.now(timezone.utc)
        return [boost for boost in self.boosts if boost.is_active(now)]

    def active_boost_weight(self, *, now: Optional[datetime] = None) -> int:
        weight = sum(max(boost.weight, 0) for boost in self.active_boosts(now=now))
        return min(weight, MAX_TOTAL_BOOST_WEIGHT)

    def add_boost(self, boost: PriorityBoost, *, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        if boost.weight <= 0:
            return

        self.prune_expired_boosts(now=now)
        boosts = list(self.boosts)
        boosts.append(boost)
        boosts.sort(key=lambda item: item.expires_at)

        while sum(max(b.weight, 0) for b in boosts if b.is_active(now)) > MAX_TOTAL_BOOST_WEIGHT:
            boosts.pop(0)

        self.boosts = [b for b in boosts if b.is_active(now)]

    def effective_priority(self, *, now: Optional[datetime] = None) -> int:
        effective = self.priority + self.active_boost_weight(now=now)
        return max(1, min(effective, 5 + MAX_TOTAL_BOOST_WEIGHT))

    def effective_priority_label(self, *, now: Optional[datetime] = None) -> str:
        base_label = _PRIORITY_LABELS.get(self.priority, f"P{self.priority}")
        boost = self.active_boost_weight(now=now)
        if boost > 0:
            return f"{base_label}+{boost}"
        return base_label

    def active_boost_kinds(self, *, now: Optional[datetime] = None) -> List[str]:
        return [boost.kind for boost in self.active_boosts(now=now)]


def _load_raw_registry(path: Path = SYMBOL_REGISTRY_PATH) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []


def load_symbol_registry(path: Path = SYMBOL_REGISTRY_PATH) -> Dict[str, SymbolRecord]:
    records: Dict[str, SymbolRecord] = {}
    for entry in _load_raw_registry(path):
        try:
            record = SymbolRecord.from_dict(entry)
        except Exception:  # noqa: BLE001
            continue
        records[record.symbol] = record
    return records


def save_symbol_registry(records: Mapping[str, SymbolRecord], path: Path = SYMBOL_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.to_dict() for record in records.values()]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def list_active_symbols(records: Mapping[str, SymbolRecord]) -> List[SymbolRecord]:
    return [record for record in records.values() if record.status == "active"]


def list_active_symbols_by_priority(records: Mapping[str, SymbolRecord]) -> List[SymbolRecord]:
    def sort_key(rec: SymbolRecord) -> tuple[int, float, str]:
        eff_priority = rec.effective_priority()
        last_refresh = _parse_iso8601(rec.last_refreshed)
        refresh_ts = last_refresh.timestamp() if last_refresh else 0.0
        return (-eff_priority, refresh_ts, rec.symbol)

    return sorted(
        (record for record in records.values() if record.status == "active"),
        key=sort_key,
    )


def update_last_refreshed(symbol: str, *, timestamp: Optional[str] = None, path: Path = SYMBOL_REGISTRY_PATH) -> None:
    records = load_symbol_registry(path)
    record = records.get(symbol.upper())
    if not record:
        return
    record.touch_refreshed(timestamp=timestamp)
    save_symbol_registry(records, path)


def bulk_update(records: MutableMapping[str, SymbolRecord], updates: Iterable[SymbolRecord]) -> None:
    for record in updates:
        records[record.symbol] = record


__all__ = [
    "SymbolRecord",
    "SYMBOL_REGISTRY_PATH",
    "load_symbol_registry",
    "save_symbol_registry",
    "list_active_symbols",
    "list_active_symbols_by_priority",
    "update_last_refreshed",
    "bulk_update",
    "MAX_TOTAL_BOOST_WEIGHT",
]


def _load_boosts(items: Iterable[Any]) -> List[PriorityBoost]:
    boosts: List[PriorityBoost] = []
    for item in items or []:
        if isinstance(item, PriorityBoost):
            boosts.append(item)
            continue
        if isinstance(item, Mapping):
            try:
                boosts.append(PriorityBoost.from_dict(item))
            except ValueError:
                continue
    return boosts
