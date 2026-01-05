"""Deterministic confidence scoring for Fundametrics metrics (Phase 17A)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, TYPE_CHECKING

from scraper.core.statements import FinancialStatement

if TYPE_CHECKING:  # pragma: no cover
    from scraper.core.metrics import MetricValue

SOURCE_WEIGHTS: Dict[str, int] = {
    "exchange": 30,
    "annual_report": 28,
    "psu_release": 26,
    "aggregator": 20,
    "scrape": 12,
}

GRADE_THRESHOLDS = (
    (85, "high"),
    (60, "medium"),
    (30, "low"),
    (1, "very_low"),
)


@dataclass(slots=True)
class ConfidenceScore:
    score: int
    grade: str
    factors: Dict[str, int]

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "score": int(self.score),
            "grade": self.grade,
        }
        if self.factors:
            payload["factors"] = self.factors
        return payload

    def cap(self, maximum: int) -> "ConfidenceScore":
        capped = max(0, min(int(maximum), int(self.score)))
        if capped == self.score:
            return self
        return ConfidenceScore(score=capped, grade=_grade_for_score(capped), factors=self.factors)


def _grade_for_score(score: int) -> str:
    if score <= 0:
        return "none"
    for threshold, grade in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "very_low"


def _parse_generated(value: Optional[object]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _source_score(source_type: Optional[str]) -> int:
    if source_type is None:
        return 0
    return SOURCE_WEIGHTS.get(source_type, SOURCE_WEIGHTS["scrape"])


def _freshness_score(
    generated_at: Optional[datetime],
    now: datetime,
    ttl_hours: Optional[int],
    ratio: Optional[float] = None,
) -> int:
    if ratio is not None:
        if ratio <= 0:
            return 25
        if ratio <= 0.25:
            return 25
        if ratio <= 0.5:
            return 18
        if ratio <= 0.75:
            return 10
        if ratio <= 1:
            return 5
        return 0

    if generated_at is None or ttl_hours is None or ttl_hours <= 0:
        return 0
    age_hours = (now - generated_at).total_seconds() / 3600
    if age_hours <= 0:
        return 25
    ratio = age_hours / ttl_hours
    if ratio <= 0.25:
        return 25
    if ratio <= 0.5:
        return 18
    if ratio <= 0.75:
        return 10
    if ratio <= 1:
        return 5
    return 0


def _statement_score(status: Optional[str]) -> int:
    if status in {"matched", "single"}:
        return 20
    if status in {"compatible", "multi"}:
        return 10
    return 0


def _completeness_score(state: Optional[str], ratio: Optional[float]) -> int:
    if ratio is not None:
        if ratio >= 0.999:
            return 15
        if ratio >= 0.5:
            return 5
        return 0
    if state == "complete":
        return 15
    if state == "partial":
        return 5
    return 0


def _stability_score(score: Optional[object]) -> int:
    if score is None:
        return 0
    try:
        numeric = int(score)
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, numeric))


def compute_confidence(
    metric: "MetricValue",
    statement: Optional[FinancialStatement],
    now: datetime,
) -> ConfidenceScore:
    """Compute deterministic confidence score for a metric."""
    if metric.value is None:
        return ConfidenceScore(score=0, grade="none", factors={})

    ctx = metric.confidence_inputs or {}

    source_type: Optional[str] = ctx.get("source_type") if isinstance(ctx.get("source_type"), str) else None
    if source_type is None and statement is not None:
        statement_sources = getattr(statement, "sources", None)
        if isinstance(statement_sources, (list, tuple)) and statement_sources:
            candidate = statement_sources[0]
            if isinstance(candidate, str):
                source_type = candidate

    generated_at = _parse_generated(ctx.get("generated_at"))
    ttl_hours = ctx.get("ttl_hours") if isinstance(ctx.get("ttl_hours"), (int, float)) else None
    freshness_ratio = None
    ratio_candidate = ctx.get("freshness_ratio")
    if isinstance(ratio_candidate, (int, float)):
        try:
            freshness_ratio = float(ratio_candidate)
        except (TypeError, ValueError):
            freshness_ratio = None
    statement_status = ctx.get("statement_status") if isinstance(ctx.get("statement_status"), str) else None
    completeness_state = ctx.get("completeness") if isinstance(ctx.get("completeness"), str) else None
    completeness_ratio = None
    comp_candidate = ctx.get("completeness_ratio")
    if isinstance(comp_candidate, (int, float)):
        try:
            completeness_ratio = float(comp_candidate)
        except (TypeError, ValueError):
            completeness_ratio = None
    stability_state = ctx.get("stability")

    factors = {
        "source": _source_score(source_type),
        "freshness": _freshness_score(
            generated_at,
            now,
            int(ttl_hours) if ttl_hours is not None else None,
            freshness_ratio,
        ),
        "statement_match": _statement_score(statement_status),
        "completeness": _completeness_score(completeness_state, completeness_ratio),
    }

    stability_value = _stability_score(stability_state)
    if stability_value:
        factors["stability"] = stability_value

    score = sum(factors.values())
    grade = _grade_for_score(score)
    return ConfidenceScore(score=score, grade=grade, factors=factors)
