"""
Structured JSON logger for Fundametrics platform.

Usage:
    from scraper.core.observability.logger import get_logger
    log = get_logger(__name__)
    log.info("scrape_completed", symbol=symbol, run_id=run_id, phase="scrape", status="ok", duration=1.23)
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class FundametricsJSONFormatter(logging.Formatter):
    """Emit one JSON object per log line with reserved fields."""

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Attach extra fields (structured context)
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "message",
            }:
                payload[key] = value

        # Ensure duration is numeric if provided
        if "duration" in payload and isinstance(payload["duration"], (int, float)):
            payload["duration"] = round(float(payload["duration"]), 3)

        return json.dumps(payload, default=str)


def setup_structured_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FundametricsJSONFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class PhaseTimer:
    """Context manager to time phases and emit structured completion logs."""

    def __init__(
        self,
        logger: logging.Logger,
        phase: str,
        symbol: Optional[str] = None,
        run_id: Optional[str] = None,
        status: str = "ok",
        **extra_fields: Any,
    ):
        self.logger = logger
        self.phase = phase
        self.symbol = symbol
        self.run_id = run_id
        self.status = status
        self.extra_fields = extra_fields
        self.start: Optional[float] = None

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start) if self.start else None
        final_status = "failed" if exc_type else self.status
        payload = {
            "phase": self.phase,
            "status": final_status,
        }
        if self.symbol:
            payload["symbol"] = self.symbol
        if self.run_id:
            payload["run_id"] = self.run_id
        if duration is not None:
            payload["duration"] = duration
        payload.update(self.extra_fields)

        if exc_type:
            self.logger.error(
                f"{self.phase}_failed",
                exc_info=True,
                **payload,
            )
        else:
            self.logger.info(
                f"{self.phase}_completed",
                **payload,
            )
