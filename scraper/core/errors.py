"""
Fundametrics-specific error hierarchy for clear classification in logs and API responses.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class FundametricsError(Exception):
    """Base class for all Fundametrics platform errors."""

    def __init__(
        self,
        message: str,
        *,
        symbol: Optional[str] = None,
        run_id: Optional[str] = None,
        phase: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.symbol = symbol
        self.run_id = run_id
        self.phase = phase
        self.details = details or {}

    def as_dict(self) -> Dict[str, Any]:
        """Serializable representation for logs/API."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "symbol": self.symbol,
            "run_id": self.run_id,
            "phase": self.phase,
            "details": self.details,
        }


class ScrapeError(FundametricsError):
    """Raised during data fetching/parsing (Screener/Trendlyne)."""

    def __init__(
        self,
        message: str,
        *,
        source: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.source = source
        self.status_code = status_code
        if source is not None:
            self.details["source"] = source
        if status_code is not None:
            self.details["status_code"] = status_code


class ValidationError(FundametricsError):
    """Raised during pipeline validation (missing fields, malformed data)."""

    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        expected: Optional[Any] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.field = field
        self.expected = expected
        if field is not None:
            self.details["field"] = field
        if expected is not None:
            self.details["expected"] = expected


class SignalError(FundametricsError):
    """Raised during signal computation (delta engine, individual engines)."""

    def __init__(
        self,
        message: str,
        *,
        signal_name: Optional[str] = None,
        engine: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.signal_name = signal_name
        self.engine = engine
        if signal_name is not None:
            self.details["signal_name"] = signal_name
        if engine is not None:
            self.details["engine"] = engine


class PersistenceError(FundametricsError):
    """Raised during read/write to DataRepository or filesystem."""

    def __init__(
        self,
        message: str,
        *,
        path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.path = path
        self.operation = operation
        if path is not None:
            self.details["path"] = path
        if operation is not None:
            self.details["operation"] = operation


class ConfigError(FundametricsError):
    """Raised on missing/invalid configuration values."""

    def __init__(
        self,
        message: str,
        *,
        key: Optional[str] = None,
        section: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.key = key
        self.section = section
        if key is not None:
            self.details["key"] = key
        if section is not None:
            self.details["section"] = section
