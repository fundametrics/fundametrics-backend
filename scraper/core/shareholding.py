"""Canonical shareholding snapshot structures and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional, Tuple

from scraper.core.statements import build_financial_statement


@dataclass(slots=True)
class ShareholdingSnapshot:
    exchange: str
    period_label: str
    as_of: date
    holders: Dict[str, float] = field(default_factory=dict)

    def normalised_holders(self) -> Dict[str, float]:
        return {key.lower(): value for key, value in self.holders.items()}


def compute_holder_delta(
    current: ShareholdingSnapshot,
    previous: Optional[ShareholdingSnapshot],
) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
    if previous is None:
        return None, "No previous snapshot"

    curr = current.normalised_holders()
    prev = previous.normalised_holders()

    if current.exchange.lower() != previous.exchange.lower():
        return None, "Incompatible shareholding snapshots"

    # Periods should be different, but holders keys should match

    if set(curr.keys()) != set(prev.keys()):
        return None, "Incompatible shareholding snapshots"

    delta = {
        holder: round(curr[holder] - prev[holder], 2)
        for holder in curr
    }
    return delta, None


def infer_snapshot_date(period_label: str) -> date:
    statement = build_financial_statement(
        period=period_label,
        scope="standalone",
        exchange="NSE",
        statement_type="shareholding",
    )
    if statement is not None:
        return statement.period_end
    return date.today()


__all__ = ["ShareholdingSnapshot", "compute_holder_delta", "infer_snapshot_date"]
