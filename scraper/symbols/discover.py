"""Symbol discovery job feeding the Fundametrics registry."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from models.symbol import (
    SYMBOL_REGISTRY_PATH,
    SymbolRecord,
    load_symbol_registry,
    save_symbol_registry,
)
from scraper.symbols.normalize import normalise_exchange, normalise_symbol
from scraper.symbols.priority import compute_priority
from scraper.symbols.sources import bse, nse


FetchCallable = Callable[[], Iterable[SymbolRecord]]


def _merge_sources(source_fetchers: Iterable[Tuple[str, FetchCallable]]) -> Iterable[SymbolRecord]:
    fetched: List[SymbolRecord] = []

    for source_name, fetcher in source_fetchers:
        try:
            records = fetcher()
        except Exception:  # noqa: BLE001
            continue
        for record in records:
            fetched.append(
                SymbolRecord(
                    symbol=normalise_symbol(record.symbol),
                    exchange=normalise_exchange(record.exchange),
                    company_name=record.company_name,
                    sector=record.sector,
                    source=source_name,
                    status="active",
                )
            )

    return fetched


def _indexed_by_symbol(records: Iterable[SymbolRecord]) -> Dict[str, SymbolRecord]:
    indexed: Dict[str, SymbolRecord] = {}
    for record in records:
        indexed[record.symbol] = record
    return indexed


def _apply_priority(record: SymbolRecord) -> None:
    record.priority = compute_priority(record)


DEFAULT_FETCHERS: List[tuple[str, FetchCallable]] = [
    ("nse", nse.fetch_symbols),
    ("bse", bse.fetch_symbols),
]


def discover_symbols(
    path=SYMBOL_REGISTRY_PATH,
    *,
    source_fetchers: Optional[Iterable[tuple[str, FetchCallable]]] = None,
) -> Dict[str, int | str]:
    registry = load_symbol_registry(path)
    seen_now = datetime.now(timezone.utc).isoformat()

    fetchers = list(source_fetchers or DEFAULT_FETCHERS)
    fetched_records = list(_merge_sources(fetchers))
    fetched_index = _indexed_by_symbol(fetched_records)

    summary_counter = Counter()

    for symbol, fetched in fetched_index.items():
        if symbol not in registry:
            fetched.touch_seen(timestamp=seen_now)
            _apply_priority(fetched)
            registry[symbol] = fetched
            summary_counter["added"] += 1
        else:
            current = registry[symbol]
            current.company_name = fetched.company_name or current.company_name
            current.sector = fetched.sector or current.sector
            current.source = fetched.source or current.source
            current.touch_seen(timestamp=seen_now)
            _apply_priority(current)
            summary_counter["updated"] += 1

    stale_cutoff = datetime.now(timezone.utc)
    for symbol, record in registry.items():
        if symbol in fetched_index:
            continue
        last_seen = record.last_seen
        if not last_seen:
            continue
        try:
            last_seen_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (stale_cutoff - last_seen_dt).days >= 30 and record.status == "active":
            record.status = "suspended"
            summary_counter["suspended"] += 1

    save_symbol_registry(registry, path)

    return {
        "added": summary_counter.get("added", 0),
        "updated": summary_counter.get("updated", 0),
        "suspended": summary_counter.get("suspended", 0),
        "total": len(registry),
        "path": str(path),
    }


__all__ = ["discover_symbols"]
