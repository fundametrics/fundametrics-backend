"""Scheduled refresh pipeline for Fundametrics ingestion.

This module scans existing processed symbols, checks TTL metadata, and issues
in-place refresh requests against the secured /admin/ingest endpoint. It is
intended to be executed by an external scheduler (cron, GitHub Actions, etc.)
and relies only on environment variables—no frontend changes required.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import httpx

from models.symbol import (
    MAX_TOTAL_BOOST_WEIGHT,
    SymbolRecord,
    list_active_symbols_by_priority,
    load_symbol_registry,
    save_symbol_registry,
)
from models.boost import PriorityBoost
from scraper.core.repository import DataRepository
from scraper.core.state import write_last_ingestion
from scraper.core.validators import (
    DEFAULT_SYMBOL_ALLOWLIST,
    SymbolValidationError,
    _normalise_allowlist,
    validate_symbol,
)
from scraper.boosts.apply import prune_expired_boosts
from scraper.refresh.budget import RefreshBudget
from scraper.refresh.decision import DecisionResult, RefreshState, evaluate_refresh

DEFAULT_TTL_HOURS = 24
LOG_DIR = Path("logs")
RECOVERY_BOOST_KIND = "refresh_failure_recovery"
RECOVERY_BOOST_WEIGHT = 1
RECOVERY_BOOST_TTL_HOURS = 1


def _load_allowlist_from_env(env_value: Optional[str]) -> Iterable[str]:
    if not env_value:
        return []
    parts = [item.strip() for item in env_value.replace("\n", ",").split(",")]
    return [item for item in parts if item]


class RefreshJobConfig:
    def __init__(self) -> None:
        self.base_url = os.getenv("INGEST_BASE_URL", "http://127.0.0.1:8000")
        self.admin_api_key = os.getenv("ADMIN_API_KEY")
        self.ingest_enabled = os.getenv("INGEST_ENABLED", "false").lower() == "true"
        self.rate_limit_seconds = max(float(os.getenv("INGEST_RATE_LIMIT_SECONDS", "5")), 0.0)
        self.max_per_run = int(os.getenv("INGEST_MAX_PER_RUN", "50"))

        allowlist_env = os.getenv("INGEST_ALLOWLIST")
        env_allowlist = _normalise_allowlist(_load_allowlist_from_env(allowlist_env))
        self.allowlist = env_allowlist or DEFAULT_SYMBOL_ALLOWLIST

    def validate(self) -> None:
        if not self.ingest_enabled:
            raise RuntimeError("Ingestion is disabled (INGEST_ENABLED != true). Abort refresh run.")
        if not self.admin_api_key:
            raise RuntimeError("ADMIN_API_KEY is required for scheduled refresh runs.")


class RefreshOrchestrator:
    def __init__(self, config: RefreshJobConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.repo = DataRepository()
        self.http_client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self.http_client.close()

    def iter_symbols(
        self,
        explicit_symbols: Optional[List[str]],
        registry: Dict[str, SymbolRecord],
    ) -> Iterable[str]:
        if explicit_symbols:
            targets = [symbol.upper().strip() for symbol in explicit_symbols if symbol]
            for symbol in targets:
                try:
                    validate_symbol(symbol, allowlist=self.config.allowlist)
                except SymbolValidationError:
                    self.logger.info("Skipping disallowed symbol %s", symbol)
                    continue
                yield symbol
            return

        if registry:
            ordered = list_active_symbols_by_priority(registry)
            for record in ordered:
                yield record.symbol
            return

        # Fallback to processed symbols on disk if registry unavailable
        targets = [symbol.upper() for symbol in self.repo.list_symbols()]
        for symbol in targets:
            yield symbol

    def load_latest_payload(self, symbol: str) -> Optional[Dict[str, any]]:
        return self.repo.get_latest(symbol)

    def call_ingest(self, symbol: str) -> Dict[str, any]:
        url = f"{self.config.base_url.rstrip('/')}/admin/ingest"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.admin_api_key,
        }
        body = {"symbol": symbol, "mode": "scheduled"}

        attempt = 0
        last_exception: Optional[Exception] = None
        while attempt < 2:
            attempt += 1
            try:
                response = self.http_client.post(url, json=body, headers=headers)
                if response.status_code in {401, 403}:
                    raise RuntimeError(f"Authentication failed (status {response.status_code})")
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as exc:  # network errors
                last_exception = exc
                self.logger.warning("Network error ingesting %s (attempt %d): %s", symbol, attempt, exc)
                time.sleep(2.0)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500 and attempt < 2:
                    last_exception = exc
                    self.logger.warning("Server error ingesting %s (attempt %d): %s", symbol, attempt, exc)
                    time.sleep(2.0)
                    continue
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Unknown ingestion failure")

    def log_result(self, symbol: str, status: str, warnings_count: int, duration_ms: int) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        self.logger.info("%s | %s | %s | %d | %d", timestamp, symbol, status, warnings_count, duration_ms)

    def _log_decision(
        self,
        action: str,
        symbol: str,
        priority_label: str,
        boosts: Optional[List[str]],
        reason: str,
    ) -> None:
        boosts_repr = f"[{', '.join(boosts)}]" if boosts else "[]"
        self.logger.info(
            "[refresh] %s %s priority=%s boosts=%s reason=%s",
            action,
            symbol,
            priority_label,
            boosts_repr,
            reason,
        )

    def run(self, explicit_symbols: Optional[List[str]] = None) -> None:
        started_at = datetime.now(timezone.utc)
        run_id = f"refresh-{started_at.strftime('%Y-%m-%dT%H-%M-%S')}"

        run_state = {
            "run_id": run_id,
            "started_at": started_at.isoformat(),
            "status": "running",
            "symbols_processed": 0,
            "failures": [],
            "warnings": 0,
            "source": "scheduled",
            "symbols": [],
        }

        write_last_ingestion(run_state)

        registry = load_symbol_registry()
        registry_changed = False

        if prune_expired_boosts(registry):
            registry_changed = True

        budget: Optional[RefreshBudget]
        if self.config.max_per_run > 0:
            budget = RefreshBudget(self.config.max_per_run)
        else:
            budget = None

        processed = 0
        success_count = 0
        failure_symbols: List[str] = []
        warnings_total = 0
        abort_error: Optional[Exception] = None

        for symbol in self.iter_symbols(explicit_symbols, registry):
            if budget and not budget.allow():
                self.logger.info(
                    "[refresh] STOP budget exhausted (max=%d)",
                    self.config.max_per_run,
                )
                break

            record = registry.get(symbol)
            now_dt = datetime.now(timezone.utc)

            if record:
                state = RefreshState(
                    failures=record.failure_count,
                    last_attempt=record.last_attempt,
                )
                decision = evaluate_refresh(record, state, now=now_dt)
                priority_label = record.effective_priority_label(now=now_dt)
                boost_kinds = record.active_boost_kinds(now=now_dt)
            else:
                temp_record = SymbolRecord(symbol=symbol, exchange="NSE")
                state = RefreshState()
                decision = DecisionResult(True, "registry miss")
                priority_label = temp_record.effective_priority_label(now=now_dt)
                boost_kinds = []

            if not decision.should_run:
                self._log_decision("SKIP", symbol, priority_label, boost_kinds, decision.reason)
                continue

            self._log_decision("RUN", symbol, priority_label, boost_kinds, decision.reason)

            start = time.perf_counter()
            attempt_timestamp = datetime.now(timezone.utc)
            attempt_iso = attempt_timestamp.isoformat()

            previous_failures = record.failure_count if record else 0

            if record:
                record.mark_attempt(timestamp=attempt_iso)
                registry_changed = True

            if budget:
                budget.consume()

            try:
                response = self.call_ingest(symbol)
            except RuntimeError as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log_result(symbol, "aborted", 0, duration_ms)
                failure_symbols.append(symbol)
                abort_error = exc
                processed += 1
                run_state["symbols"].append(symbol)

                if record:
                    record.record_failure(timestamp=datetime.now(timezone.utc).isoformat())
                    registry_changed = True

                run_state.update(
                    {
                        "symbols_processed": processed,
                        "warnings": warnings_total,
                        "failures": failure_symbols.copy(),
                    }
                )
                write_last_ingestion(run_state)
                break
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed ingest for %s: %s", symbol, exc)
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.log_result(symbol, "failed", 0, duration_ms)
                failure_symbols.append(symbol)
                processed += 1
                run_state["symbols"].append(symbol)

                if record:
                    record.record_failure(timestamp=datetime.now(timezone.utc).isoformat())
                    registry_changed = True

                run_state.update(
                    {
                        "symbols_processed": processed,
                        "failures": failure_symbols.copy(),
                        "warnings": warnings_total,
                    }
                )
                write_last_ingestion(run_state)
                continue

            warnings = response.get("warnings")
            warnings_count = len(warnings) if isinstance(warnings, list) else 0
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.log_result(symbol, "success", warnings_count, duration_ms)

            processed += 1
            success_count += 1
            warnings_total += warnings_count
            run_state["symbols"].append(symbol)

            if symbol in registry:
                refresh_timestamp = datetime.now(timezone.utc).isoformat()
                registry[symbol].record_success(timestamp=refresh_timestamp)
                if previous_failures > 0:
                    recovery_boost = PriorityBoost(
                        kind=RECOVERY_BOOST_KIND,
                        weight=min(RECOVERY_BOOST_WEIGHT, MAX_TOTAL_BOOST_WEIGHT),
                        expires_at=datetime.fromisoformat(refresh_timestamp.replace("Z", "+00:00"))
                        + timedelta(hours=RECOVERY_BOOST_TTL_HOURS),
                        source="scheduler",
                    )
                    registry[symbol].add_boost(recovery_boost)
                registry_changed = True

            run_state.update(
                {
                    "symbols_processed": processed,
                    "warnings": warnings_total,
                    "failures": failure_symbols.copy(),
                }
            )
            write_last_ingestion(run_state)

            if self.config.rate_limit_seconds > 0:
                time.sleep(self.config.rate_limit_seconds)

        finished_at = datetime.now(timezone.utc)

        if abort_error is not None:
            status = "failed" if success_count == 0 else "partial"
        elif failure_symbols and success_count > 0:
            status = "partial"
        elif failure_symbols and success_count == 0:
            status = "failed"
        else:
            status = "success"

        run_state.update(
            {
                "status": status,
                "finished_at": finished_at.isoformat(),
                "symbols_processed": processed,
                "failures": failure_symbols,
                "warnings": warnings_total,
            }
        )

        write_last_ingestion(run_state)

        if registry and registry_changed:
            save_symbol_registry(registry)

        if abort_error is not None:
            raise abort_error


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"refresh-{datetime.now(timezone.utc).date()}.log"

    logger = logging.getLogger("fundametrics.refresh")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fundametrics scheduled refresh runner")
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Limit refresh run to specific symbol(s). Repeat for multiple symbols.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = RefreshJobConfig()
    config.validate()

    logger = setup_logger()
    orchestrator = RefreshOrchestrator(config, logger)

    try:
        orchestrator.run(explicit_symbols=args.symbols)
    finally:
        orchestrator.close()


if __name__ == "__main__":
    main()
