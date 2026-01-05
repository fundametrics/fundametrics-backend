#!/usr/bin/env python3
"""
Fundametrics Stock Scraper - Main Entry Point
======================================

Production-grade web scraping system for Indian stock fundamental data.

Usage:
    python main.py                  # Run in default mode
    python main.py --mode scraper   # Run scraper once
    python main.py --mode scheduler # Run scheduled scraper
    python main.py --mode api       # Run API server
    python main.py --help           # Show help
"""

import sys
import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Iterable, Union
import uuid
from scraper.core.signals.delta import RunDeltaEngine
from scraper.core.config import Config

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scraper.utils.logger import setup_logging, get_logger
from scraper.core.fetcher import Fetcher
from scraper.sources.screener import ScreenerScraper
from scraper.sources.trendlyne import TrendlyneScraper
from scraper.core.api_response_builder import FundametricsResponseBuilder
from scraper.core.data_pipeline import DataPipeline
from scraper.core.repository import DataRepository
from dotenv import load_dotenv


DEFAULT_SYMBOLS: List[str] = ["COALINDIA", "ONGC", "MRF"]


def _resolve_symbols(args) -> List[str]:
    """Determine which symbols to scrape based on CLI arguments."""
    symbols: List[str] = []

    if getattr(args, "symbol", None):
        symbols.append(args.symbol.upper())

    if getattr(args, "symbols", None):
        bulk = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
        symbols.extend(bulk)

    if not symbols:
        return DEFAULT_SYMBOLS.copy()

    # Preserve order while removing duplicates
    seen = set()
    deduped: List[str] = []
    for sym in symbols:
        if sym not in seen:
            deduped.append(sym)
            seen.add(sym)
    return deduped


def run_scraper(
    symbol: Optional[str] = None,
    *,
    symbols: Optional[Iterable[str]] = None,
    shareholding: Optional[bool] = None,
    trendlyne: Optional[bool] = None,
    signals: Optional[bool] = None,
    output_dir: Optional[Union[str, Path]] = None,
    persist_runs: Optional[bool] = None,
    delta_engine: Optional[RunDeltaEngine] = None,
) -> List[str]:
    pipeline = DataPipeline()
    delta_engine = delta_engine or RunDeltaEngine()
    persist_runs_flag = (
        persist_runs
        if persist_runs is not None
        else Config.get("data", "persist_runs", default=True)
    )
    enable_signals = (
        signals
        if signals is not None
        else Config.get("features", "enable_signals", default=True)
    )
    # ... rest of the function remains the same ...
