"""Refresh decision engine based on policy and cooldown state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from models.symbol import SymbolRecord
from scraper.refresh.cooldown import is_in_cooldown, next_allowed_time
from scraper.refresh.policy import get_priority_interval


@dataclass(slots=True)
class RefreshState:
    failures: int = 0
    last_attempt: Optional[str] = None

    def last_attempt_timestamp(self) -> Optional[float]:
        if not self.last_attempt:
            return None
        try:
            dt = datetime.fromisoformat(self.last_attempt.replace("Z", "+00:00"))
            return dt.timestamp()
        except ValueError:
            return None

@dataclass(slots=True)
class DecisionResult:
    should_run: bool
    reason: str


def evaluate_refresh(symbol: SymbolRecord, state: RefreshState, *, now: Optional[datetime] = None) -> DecisionResult:
    now = now or datetime.now(timezone.utc)
    now_ts = now.timestamp()

    if symbol.status != "active":
        return DecisionResult(False, f"inactive status={symbol.status}")

    last_attempt_ts = state.last_attempt_timestamp()
    if is_in_cooldown(failures=state.failures, last_attempt_ts=last_attempt_ts, now_ts=now_ts):
        next_time = next_allowed_time(state.failures, last_attempt_ts or now_ts)
        wait_secs = max(0, int(next_time - now_ts))
        return DecisionResult(False, f"cooldown active ({wait_secs}s remaining)")

    interval = get_priority_interval(symbol.priority)
    last_refreshed = symbol.last_refreshed
    if not last_refreshed:
        return DecisionResult(True, "never refreshed")

    try:
        refreshed_dt = datetime.fromisoformat(last_refreshed.replace("Z", "+00:00"))
    except ValueError:
        return DecisionResult(True, "invalid last_refreshed timestamp")

    elapsed = now_ts - refreshed_dt.timestamp()
    if elapsed >= interval:
        overdue = int(elapsed - interval)
        return DecisionResult(True, f"stale by {overdue}s")

    remaining = int(interval - elapsed)
    return DecisionResult(False, f"fresh (next refresh in {remaining}s)")


def should_refresh(symbol: SymbolRecord, state: RefreshState, *, now: Optional[datetime] = None) -> bool:
    return evaluate_refresh(symbol, state, now=now).should_run


__all__ = ["RefreshState", "DecisionResult", "evaluate_refresh", "should_refresh"]
