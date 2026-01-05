from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from dotenv import load_dotenv

from scraper.core.api_response_builder import FundametricsResponseBuilder
from scraper.core.config import Config
from scraper.core.data_pipeline import DataPipeline
from scraper.core.fetcher import Fetcher
from scraper.core.repository import DataRepository
from scraper.sources.screener import ScreenerScraper
from scraper.sources.trendlyne import TrendlyneScraper
from scraper.utils.logger import get_logger, setup_logging

DEFAULT_SYMBOLS: List[str] = ["COALINDIA", "ONGC", "MRF"]


def load_symbol_roster(symbol: Optional[str] = None) -> List[str]:
    """Resolve the list of symbols to process based on config and overrides."""
    if symbol:
        return [symbol.upper()]

    symbols_file = Config.get("data", "symbols_file")
    if symbols_file:
        file_path = Path(symbols_file)
        if file_path.exists():
            contents = [line.strip().upper() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if contents:
                return contents

    return DEFAULT_SYMBOLS.copy()


def _safe_metadata(dict_like: Dict[str, Any]) -> Dict[str, Any]:
    return dict(dict_like) if isinstance(dict_like, dict) else {}


def _sanitize_metadata(clean_data: Dict[str, Any]) -> None:
    clean_data.pop("source", None)
    metadata = clean_data.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("source", None)
        metadata.pop("source_url", None)


def _provenance_block() -> Dict[str, Any]:
    return {
        "generated_by": "fundametrics",
        "pipeline_version": "1.0",
        "computation_mode": "internal",
        "recomputable": True,
    }


async def _scrape_symbol(
    symbol: str,
    screener: ScreenerScraper,
    trendlyne: Optional[TrendlyneScraper],
    pipeline: DataPipeline,
    repository: Optional[DataRepository],
    output_dir: Path,
    enable_shareholding: bool,
) -> str:
    log = get_logger(__name__)

    log.info("Scraping {}", symbol)
    financial_data = await screener.scrape_stock(symbol)
    if not financial_data:
        raise RuntimeError("Financial source returned no data")
    if not enable_shareholding:
        financial_data.pop("shareholding", None)

    profile_data: Dict[str, Any] = {}
    if trendlyne:
        profile_data = await trendlyne.scrape_stock(symbol) or {}

    raw_metadata = _safe_metadata(financial_data.get("metadata", {}))
    metadata = {
        **raw_metadata,
        "company_name": profile_data.get("company_name") or raw_metadata.get("company_name") or symbol,
        "symbol": symbol,
        "sector": profile_data.get("sector") or raw_metadata.get("sector"),
        "industry": profile_data.get("industry") or raw_metadata.get("industry"),
    }

    raw_payload = {
        "symbol": symbol,
        "metadata": metadata,
        "financials": financial_data.get("financials", {}),
        "shareholding": financial_data.get("shareholding") if enable_shareholding else None,
        "profile": profile_data,
        "source": {}
    }

    pipeline_result = pipeline.process(raw_payload)
    clean_data = pipeline_result.get("clean_data", {}) or {}
    validation_report = pipeline_result.get("validation_report", {}) or {}

    _sanitize_metadata(clean_data)
    if not enable_shareholding:
        clean_data.pop("shareholding", None)

    provenance = _provenance_block()

    builder = FundametricsResponseBuilder(
        symbol=symbol,
        company_name=clean_data.get("metadata", {}).get("company_name")
        or metadata.get("company_name")
        or symbol,
        sector=clean_data.get("metadata", {}).get("sector")
        or metadata.get("sector")
        or "Unknown",
    )

    builder.set_company_metadata(clean_data.get("metadata"))

    financials = clean_data.get("financials", {}) or {}
    income_statement = financials.get("income_statement")
    if income_statement:
        builder.add_income_statement(income_statement)

    balance_sheet = financials.get("balance_sheet")
    if balance_sheet:
        builder.add_balance_sheet(balance_sheet)

    quarters = financials.get("quarters")
    if quarters:
        builder.set_quarterly_financials(quarters)

    cash_flow = financials.get("cash_flow")
    if cash_flow:
        builder.add_cash_flow(cash_flow)

    shareholding_block = clean_data.get("shareholding") if enable_shareholding else None
    if shareholding_block:
        builder.add_shareholding(shareholding_block)

    # Drop raw shareholding tables from persisted clean data
    if "shareholding" in clean_data:
        clean_data.pop("shareholding", None)

    response = builder.build()
    response.setdefault("metadata", {})
    response["metadata"]["validation_status"] = validation_report.get("status")
    response["metadata"]["provenance"] = provenance.copy()

    shareholding_payload = response.get("shareholding") or {
        "status": "unavailable",
        "summary": {},
        "insights": [],
    }
    if not isinstance(shareholding_payload.get("summary"), dict):
        shareholding_payload["summary"] = {}
    if not isinstance(shareholding_payload.get("insights"), list):
        shareholding_payload["insights"] = []

    run_id = str(uuid.uuid4())
    run_timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    response["metadata"]["run_id"] = run_id
    response["metadata"]["run_timestamp"] = run_timestamp

    run_payload = {
        "symbol": symbol,
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "validation": validation_report,
        "data": clean_data,
        "metrics": response.get("financials", {}).get("metrics", {}),
        "fundametrics_response": response,
        "provenance": provenance,
        "shareholding": shareholding_payload,
    }

    if repository:
        repository.save_run(symbol=symbol, run_id=run_id, payload=run_payload)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol.lower()}_{timestamp}.json"
    output_path.write_text(json.dumps(response, indent=2), encoding="utf-8")

    log.success("Run completed", symbol=symbol, run_id=run_id, validation_status=validation_report.get("status"))
    return run_id


def run_scraper(
    symbol: Optional[str] = None,
    *,
    symbols: Optional[Iterable[str]] = None,
    shareholding: Optional[bool] = None,
    trendlyne: Optional[bool] = None,
    output_dir: Optional[Union[str, Path]] = None,
    persist_runs: Optional[bool] = None,
) -> List[str]:
    """Public entry point used by CLI, scheduler, and tests."""
    setup_logging()
    load_dotenv()
    log = get_logger(__name__)

    cfg = Config.load()
    enable_screener = Config.get("sources", "enable_screener", default=True)
    if not enable_screener:
        raise RuntimeError("Screener source is disabled via configuration")

    enable_trendlyne = trendlyne if trendlyne is not None else Config.get("sources", "enable_trendlyne", default=True)
    enable_shareholding = shareholding if shareholding is not None else Config.get("sources", "enable_shareholding", default=True)
    persist_runs_flag = Config.get("data", "persist_runs", default=True)
    if persist_runs is not None:
        persist_runs_flag = persist_runs

    output_dir_path = Path(output_dir) if output_dir is not None else Path(
        Config.get("data", "output_dir", default="data/processed")
    )

    symbol_list = list(symbols) if symbols else load_symbol_roster(symbol)
    if not symbol_list:
        log.warning("No symbols resolved for run")
        return []

    repository = DataRepository(base_dir=output_dir_path) if persist_runs_flag else None

    fetcher = Fetcher()
    screener = ScreenerScraper(fetcher)
    trendlyne = TrendlyneScraper(fetcher) if enable_trendlyne else None
    pipeline = DataPipeline()

    async def _run_all(targets: List[str]) -> List[str]:
        run_ids: List[str] = []
        for sym in targets:
            try:
                run_id = await _scrape_symbol(
                    symbol=sym,
                    screener=screener,
                    trendlyne=trendlyne,
                    pipeline=pipeline,
                    repository=repository,
                    output_dir=output_dir_path,
                    enable_shareholding=enable_shareholding,
                )
                run_ids.append(run_id)
            except Exception as exc:  # noqa: BLE001
                log.exception("Failed to process {}: {}", sym, exc)
        return run_ids

    return asyncio.run(_run_all(symbol_list))


__all__ = ["run_scraper", "load_symbol_roster"]
