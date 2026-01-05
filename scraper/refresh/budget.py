"""Refresh budget controller for per-run limits."""

from __future__ import annotations


class RefreshBudget:
    def __init__(self, max_items: int) -> None:
        if max_items < 0:
            raise ValueError("max_items must be non-negative")
        self.remaining = max_items

    def allow(self) -> bool:
        return self.remaining > 0

    def consume(self) -> None:
        if not self.allow():
            raise RuntimeError("Budget exceeded")
        self.remaining -= 1


__all__ = ["RefreshBudget"]
