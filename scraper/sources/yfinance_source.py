"""
Yahoo Finance Data Source for Fundametrics
==========================================

Provides real-time market data and historical financials via yfinance.
Used as:
  1. Live price/market data endpoint (no caching)
  2. Gap-filler for missing Screener fundamentals
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import math

from scraper.utils.logger import get_logger
from scraper.core.errors import ScrapeError

log = get_logger(__name__)


def _safe_get(info: dict, key: str) -> Any:
    """Return value from yfinance info dict, converting NaN/inf to None."""
    val = info.get(key)
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def get_live_data(symbol: str) -> dict:
    """
    Fetch current price, PE, PB, market cap, 52-week range, sector and industry.

    Args:
        symbol: NSE stock symbol (e.g. 'RELIANCE'). '.NS' is appended automatically.

    Returns:
        dict with live market snapshot fields.

    Raises:
        ScrapeError on any failure.
    """
    run_id = str(uuid.uuid4())[:8]
    log.info("yfinance live fetch starting", symbol=symbol, run_id=run_id, phase="live_data")

    try:
        import yfinance as yf

        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}

        result = {
            "symbol": symbol,
            "price": _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice"),
            "previous_close": _safe_get(info, "previousClose") or _safe_get(info, "regularMarketPreviousClose"),
            "pe_ratio": _safe_get(info, "trailingPE"),
            "forward_pe": _safe_get(info, "forwardPE"),
            "pb_ratio": _safe_get(info, "priceToBook"),
            "market_cap": _safe_get(info, "marketCap"),
            "fifty_two_week_high": _safe_get(info, "fiftyTwoWeekHigh"),
            "fifty_two_week_low": _safe_get(info, "fiftyTwoWeekLow"),
            "sector": _safe_get(info, "sector"),
            "industry": _safe_get(info, "industry"),
            "dividend_yield": _safe_get(info, "dividendYield"),
            "beta": _safe_get(info, "beta"),
            "volume": _safe_get(info, "volume"),
            "average_volume": _safe_get(info, "averageVolume"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        log.info(
            "yfinance live fetch complete",
            symbol=symbol,
            run_id=run_id,
            phase="live_data",
            price=result["price"],
        )
        return result

    except Exception as exc:
        log.error("yfinance live fetch failed", symbol=symbol, run_id=run_id, phase="live_data", error=str(exc))
        raise ScrapeError(
            f"yfinance live data failed for {symbol}: {exc}",
            source="yfinance",
            symbol=symbol,
            run_id=run_id,
            phase="live_data",
        ) from exc


def get_raw_financials(symbol: str) -> dict:
    """
    Fetch last 4 years of income statement, balance sheet, and cash flow from yfinance.

    All pandas Timestamps are converted to ISO strings; NaN values become None.

    Args:
        symbol: NSE stock symbol.

    Returns:
        dict with keys 'income_statement', 'balance_sheet', 'cash_flow', each
        being a dict of {period_str: {line_item: value}}.

    Raises:
        ScrapeError on failure.
    """
    run_id = str(uuid.uuid4())[:8]
    log.info("yfinance financials fetch starting", symbol=symbol, run_id=run_id, phase="raw_financials")

    try:
        import yfinance as yf
        import pandas as pd

        ticker = yf.Ticker(f"{symbol}.NS")

        def _df_to_dict(df: Optional[Any]) -> dict:
            """Convert a yfinance DataFrame to {period: {item: value}} dict."""
            if df is None or (hasattr(df, "empty") and df.empty):
                return {}
            out: Dict[str, Dict[str, Any]] = {}
            for col in df.columns:
                period_key = col.isoformat() if hasattr(col, "isoformat") else str(col)
                row_dict: Dict[str, Any] = {}
                for idx in df.index:
                    val = df.at[idx, col]
                    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                        val = None
                    elif hasattr(val, "item"):
                        val = val.item()
                    row_dict[str(idx)] = val
                out[period_key] = row_dict
            return out

        result = {
            "symbol": symbol,
            "income_statement": _df_to_dict(ticker.financials),
            "balance_sheet": _df_to_dict(ticker.balance_sheet),
            "cash_flow": _df_to_dict(ticker.cashflow),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        total_periods = (
            len(result["income_statement"])
            + len(result["balance_sheet"])
            + len(result["cash_flow"])
        )
        log.info(
            "yfinance financials fetch complete",
            symbol=symbol,
            run_id=run_id,
            phase="raw_financials",
            total_periods=total_periods,
        )
        return result

    except Exception as exc:
        log.error("yfinance financials fetch failed", symbol=symbol, run_id=run_id, phase="raw_financials", error=str(exc))
        raise ScrapeError(
            f"yfinance financials failed for {symbol}: {exc}",
            source="yfinance",
            symbol=symbol,
            run_id=run_id,
            phase="raw_financials",
        ) from exc
