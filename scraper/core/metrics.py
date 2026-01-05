"""Metric value abstractions with provenance metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

if __name__ == "typing":  # pragma: no cover - typing sentinel for static analyzers
    from scraper.core.confidence import ConfidenceScore  # type: ignore # noqa: F401


@dataclass(slots=True)
class MetricValue:
    value: Optional[float]
    unit: str
    statement_id: Optional[str]
    computed: bool = False
    reason: Optional[str] = None
    confidence: Optional["ConfidenceScore"] = None
    confidence_inputs: Optional[Dict[str, object]] = None

    def is_present(self) -> bool:
        return self.value is not None


__all__ = ["MetricValue"]
