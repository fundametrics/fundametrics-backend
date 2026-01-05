"""Fundametrics base signal primitives.

All Fundametrics-owned signal engines should build on these definitions.
Signals must never reference third-party labels or raw scraped tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Protocol

Severity = str  # Expected values: "low", "medium", "high"


def normalize_severity(score: float) -> Severity:
    """Map a 0.0–1.0 score to Fundametrics severity buckets."""
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


@dataclass(frozen=True)
class FundametricsSignal:
    """Canonical Fundametrics signal representation."""

    signal: str
    severity: Severity
    confidence: float
    explanation: str
    timestamp: datetime
    metadata: Dict[str, Any] | None = None

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable view of the signal."""
        return {
            "signal": self.signal,
            "severity": self.severity,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }


class Signal(Protocol):
    """Protocol implemented by concrete signal calculators."""

    name: str

    def evaluate(self, context: Dict[str, Any]) -> FundametricsSignal:
        ...


class BaseSignalEngine:
    """Shared utilities for signal engines."""

    ENGINE_NAME = "base"

    def compute(self, *_args, **_kwargs) -> List[FundametricsSignal]:
        raise NotImplementedError("Signal engines must implement compute()")

    @staticmethod
    def clamp_confidence(value: float) -> float:
        """Clamp a confidence score to the 0–1 range."""
        return max(0.0, min(1.0, value))

    @staticmethod
    def now() -> datetime:
        """Return a timezone-aware UTC timestamp."""
        return datetime.now(timezone.utc)


__all__ = [
    "Severity",
    "normalize_severity",
    "FundametricsSignal",
    "Signal",
    "BaseSignalEngine",
]

