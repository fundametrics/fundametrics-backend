"""Persistence helpers for ingestion run state."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

STATE_DIR = Path("data/system")
LAST_INGESTION_PATH = STATE_DIR / "last_ingestion.json"


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_last_ingestion() -> Optional[Dict[str, Any]]:
    """Return the most recent recorded ingestion run state, if available."""

    if not LAST_INGESTION_PATH.exists():
        return None

    try:
        with LAST_INGESTION_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def write_last_ingestion(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically persist ingestion run metadata and return the stored payload."""

    _ensure_state_dir()
    stored = {
        **payload,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    fd, tmp_path = tempfile.mkstemp(prefix="ingestion_state_", suffix=".json", dir=STATE_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(stored, tmp_file, indent=2, sort_keys=True)
        os.replace(tmp_path, LAST_INGESTION_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return stored


__all__ = ["load_last_ingestion", "write_last_ingestion", "LAST_INGESTION_PATH"]
