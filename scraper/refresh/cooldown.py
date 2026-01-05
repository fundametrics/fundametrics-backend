"""Cooldown logic to prevent hammering failing symbols."""

from __future__ import annotations

from typing import Optional

MAX_BACKOFF_SECONDS = 24 * 60 * 60  # 24 hours
BASE_BACKOFF_SECONDS = 5 * 60  # 5 minutes


def next_allowed_time(failures: int, last_attempt_ts: float) -> float:
    multiplier = max(failures, 0)
    backoff = min((2 ** multiplier) * BASE_BACKOFF_SECONDS, MAX_BACKOFF_SECONDS)
    return last_attempt_ts + backoff


def is_in_cooldown(*, failures: int, last_attempt_ts: Optional[float], now_ts: float) -> bool:
    if failures <= 0 or last_attempt_ts is None:
        return False
    return now_ts < next_allowed_time(failures, last_attempt_ts)


__all__ = ["next_allowed_time", "is_in_cooldown", "MAX_BACKOFF_SECONDS", "BASE_BACKOFF_SECONDS"]
