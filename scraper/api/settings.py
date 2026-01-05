"""Runtime settings for the Fundametrics API layer."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Iterable, Set

from scraper.core.validators import DEFAULT_SYMBOL_ALLOWLIST, _normalise_allowlist


class ApiSettings:
    """Container for runtime-tunable API settings."""

    def __init__(self) -> None:
        self.ingest_enabled: bool = os.getenv("INGEST_ENABLED", "true").lower() == "true"
        self.admin_api_key: str | None = os.getenv("ADMIN_API_KEY") or None
        self.ingest_allowlist: Set[str] = self._load_allowlist()
        self.ingest_rate_limit_seconds: float = max(float(os.getenv("INGEST_RATE_LIMIT_SECONDS", "5")), 0.0)
        self.ingest_max_per_run: int = max(int(os.getenv("INGEST_MAX_PER_RUN", "50")), 0)

    @property
    def admin_key_configured(self) -> bool:
        return bool(self.admin_api_key)

    @property
    def safe_to_run_refresh(self) -> bool:
        if not self.ingest_enabled or not self.admin_key_configured:
            return False
        # Consider rate limits below 1 second as risky bursts.
        return self.ingest_rate_limit_seconds >= 1.0

    @staticmethod
    def _env_list(var_name: str) -> Iterable[str]:
        raw = os.getenv(var_name)
        if not raw:
            return []
        # Accept comma or whitespace separated lists
        parts = [item.strip() for item in raw.replace("\n", ",").split(",")]
        return [item for item in parts if item]

    def _load_allowlist(self) -> Set[str]:
        overrides = _normalise_allowlist(self._env_list("INGEST_ALLOWLIST"))
        if overrides:
            return overrides
        return DEFAULT_SYMBOL_ALLOWLIST.copy()


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    """Return cached API settings instance."""

    return ApiSettings()


__all__ = ["ApiSettings", "get_api_settings"]
