"""Priority boost model definition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional


@dataclass(slots=True)
class PriorityBoost:
    kind: str
    weight: int
    expires_at: datetime
    source: str

    def is_active(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now < self.expires_at

    def to_dict(self) -> Mapping[str, str | int]:
        return {
            "kind": self.kind,
            "weight": self.weight,
            "expires_at": self.expires_at.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "PriorityBoost":
        expires_raw = payload.get("expires_at")
        expires_at = _parse_iso8601(expires_raw) if isinstance(expires_raw, str) else None
        if expires_at is None:
            raise ValueError("expires_at is required for PriorityBoost")
        return cls(
            kind=str(payload.get("kind", "unknown")),
            weight=int(payload.get("weight", 0) or 0),
            expires_at=expires_at,
            source=str(payload.get("source", "unknown")),
        )


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


__all__ = ["PriorityBoost"]
