"""Local JSON repository for Fundametrics pipeline outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DataRepository:
    """Persist pipeline results on the local filesystem."""

    def __init__(self, base_dir: Path | str = Path("data/processed")) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, *, symbol: str, run_id: str, payload: Dict[str, Any]) -> None:
        """Persist a single run payload to disk."""
        if not run_id:
            raise ValueError("run_id is required to persist a run")

        symbol_dir = self._symbol_dir(symbol)
        symbol_dir.mkdir(parents=True, exist_ok=True)

        target_path = symbol_dir / f"{run_id}.json"
        with target_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)

    def list_symbols(self) -> List[str]:
        """Return all symbols that have at least one stored run."""
        if not self.base_dir.exists():
            return []

        symbols = [path.name for path in self.base_dir.iterdir() if path.is_dir()]
        return sorted(symbols)

    def get_latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Return the most recent run payload for the symbol."""
        symbol_dir = self._symbol_dir(symbol)
        if not symbol_dir.exists():
            return None

        # Prioritize 'latest.json' if it specifically exists
        latest_path = symbol_dir / "latest.json"
        if latest_path.exists():
            return self._read_json(latest_path)

        # Fallback to alphabetically last (usually timestamped)
        files = sorted(symbol_dir.glob("*.json"), reverse=True)
        if not files:
            return None

        return self._read_json(files[0])

    def list_runs(self, symbol: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return metadata for historical runs, newest first."""
        symbol_dir = self._symbol_dir(symbol)
        if not symbol_dir.exists():
            return []

        files = sorted(symbol_dir.glob("*.json"), reverse=True)
        if limit is not None:
            files = files[:limit]

        runs: List[Dict[str, Any]] = []
        for path in files:
            payload = self._read_json(path)
            runs.append(
                {
                    "run_id": payload.get("run_id"),
                    "run_timestamp": payload.get("run_timestamp"),
                    "validation_status": payload.get("validation", {}).get("status"),
                }
            )
        return runs

    def load_runs(self, symbol: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return full run payloads, oldest to newest."""
        symbol_dir = self._symbol_dir(symbol)
        if not symbol_dir.exists():
            return []

        files = sorted(symbol_dir.glob("*.json"))
        if limit is not None:
            files = files[-limit:]

        runs: List[Dict[str, Any]] = []
        for path in files:
            runs.append(self._read_json(path))
        return runs

    # ------------------------------------------------------------------
    def _symbol_dir(self, symbol: str) -> Path:
        return self.base_dir / symbol.lower()

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as fp:
            return json.load(fp)
