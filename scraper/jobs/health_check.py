"""Health gate utility for scheduled refresh workflows."""

from __future__ import annotations

import json
import os
from typing import Final

import httpx


def _log(message: str) -> None:
    print(f"[health-check] {message}", flush=True)


def _write_output(refresh_ready: bool, reason: str) -> None:
    reason_clean = reason.replace("\n", " ")
    output_lines = [
        f"refresh_ready={'true' if refresh_ready else 'false'}",
        f"reason={reason_clean}",
    ]

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            for line in output_lines:
                handle.write(f"{line}\n")


def main() -> None:
    base_url: str = os.getenv("INGEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    endpoint: Final[str] = f"{base_url}/admin/health"
    admin_key = os.getenv("ADMIN_API_KEY")

    headers = {"Accept": "application/json"}
    if admin_key:
        headers["x-api-key"] = admin_key

    _log(f"Checking pipeline health at {endpoint}")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(endpoint, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        _log(f"Health endpoint returned HTTP {exc.response.status_code}: {exc}")
        _write_output(False, reason=f"http_error:{exc.response.status_code}")
        return
    except (httpx.RequestError, json.JSONDecodeError) as exc:
        _log(f"Failed to evaluate health endpoint: {exc}")
        _write_output(False, reason="request_failed")
        return

    status = str(payload.get("status", "unknown")).lower()
    warnings_total = payload.get("warnings", {}).get("total")
    stale_count = payload.get("symbols", {}).get("stale")

    _log(
        "Health snapshot -> status=%s stale=%s warnings=%s"
        % (status, stale_count, warnings_total)
    )

    allowed_statuses = {"healthy", "degraded"}
    if status not in allowed_statuses:
        _log(
            "Skipping scheduled refresh because pipeline status '%s' is outside %s"
            % (status, sorted(allowed_statuses))
        )
        _write_output(False, reason=f"status:{status}")
        return

    _log("Pipeline healthy enough for refresh. Proceeding.")
    _write_output(True, reason=status)


if __name__ == "__main__":
    main()
