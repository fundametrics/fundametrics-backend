"""Refresh interval policy derived from symbol priority."""

from __future__ import annotations

from typing import Dict

PRIORITY_INTERVALS: Dict[int, int] = {
    5: 15 * 60,
    4: 60 * 60,
    3: 6 * 60 * 60,
    2: 24 * 60 * 60,
    1: 7 * 24 * 60 * 60,
}

DEFAULT_INTERVAL = PRIORITY_INTERVALS[2]


def get_priority_interval(priority: int) -> int:
    return PRIORITY_INTERVALS.get(priority, DEFAULT_INTERVAL)


__all__ = ["PRIORITY_INTERVALS", "get_priority_interval"]
