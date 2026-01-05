"""Storage helpers for ingestion snapshots."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def _symbol_dir(symbol: str) -> Path:
    base = Path("data/processed")
    return base / symbol.lower()


def write_company_snapshot(symbol: str, payload: Dict) -> str:
    """Persist a company payload atomically as latest and timestamped copies.

    Args:
        symbol: Normalised stock symbol.
        payload: JSON-serialisable dictionary representing the latest run.

    Returns:
        ISO timestamp (UTC) when the payload was stored.
    """

    target_dir = _symbol_dir(symbol)
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    # Ensure deterministic ordering for diffs.
    temp_fd, temp_path = tempfile.mkstemp(prefix="ingest_", suffix=".json", dir=target_dir)
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as temp_file:
            json.dump(payload, temp_file, indent=2, sort_keys=True)

        latest_path = target_dir / "latest.json"
        os.replace(temp_path, latest_path)

        dated_filename = f"{stored_at.replace(':', '-')}Z.json"
        dated_path = target_dir / dated_filename
        with dated_path.open("w", encoding="utf-8") as dated_file:
            json.dump(payload, dated_file, indent=2, sort_keys=True)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return stored_at


__all__ = ["write_company_snapshot"]
