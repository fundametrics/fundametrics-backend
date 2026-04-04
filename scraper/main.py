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
        "pipeline_version": "2.0",
        "computation_mode": "internal",
        "recomputable": True,
    }


def _compute_completeness_score(response: Dict[str, Any]) -> float:
    """Compute data_completeness_score: ratio of populated fields to expected fields."""
    expected_keys = [
        "symbol", "company",
        # Financials
        "financials.latest", "financials.metrics", "financials.ratios",
        "financials.income_statement", "financials.balance_sheet", "financials.cash_flow",
        # Metrics
        "metrics.values", "metrics.ratios",
        # Shareholding
        "shareholding.summary",
    ]

    populated = 0
    total = len(expected_keys)

    for key_path in expected_keys:
        parts = key_path.split(".")
        obj = response
        found = True
        for part in parts:
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                found = False
                break
        if found and obj not in (None, {}, [], ""):
            populated += 1

    return round(populated / total, 3) if total > 0 else 0.0


def _build_quality_report(response: Dict[str, Any], data_sources: List[str]) -> Dict[str, Any]:
    """Build Phase 8 quality report for run payload."""
    completeness = _compute_completeness_score(response)

    # Check for missing fields
    missing_fields = []
    metrics = response.get("financials", {}).get("metrics", {})
    expected_metrics = [
        "fundametrics_operating_margin", "fundametrics_return_on_equity",
        "fundametrics_eps", "fundametrics_market_cap",
        "fundametrics_pe_ratio", "fundametrics_debt_to_equity",
    ]
    for key in expected_metrics:
        val = metrics.get(key, {})
        if isinstance(val, dict) and val.get("value") is None:
            missing_fields.append(key)
        elif val is None:
            missing_fields.append(key)

    # Anomaly detection
    anomaly_flags = []
    roe_val = metrics.get("fundametrics_return_on_equity", {})
    if isinstance(roe_val, dict) and roe_val.get("value") is not None:
        if abs(roe_val["value"]) > 100:
            anomaly_flags.append(f"ROE = {roe_val['value']}% (unusually high)")

    revenue = response.get("financials", {}).get("latest", {}).get("revenue", {})
    if isinstance(revenue, dict) and revenue.get("value") is not None:
        if revenue["value"] < 0:
            anomaly_flags.append(f"Negative revenue: {revenue['value']}")

    # Source breakdown
    source_breakdown = {}
    for src in data_sources:
        source_breakdown[src] = "populated"

    return {
        "completeness_score": completeness,
        "source_breakdown": source_breakdown,
        "missing_fields": missing_fields,
        "stale_fields": [],  # TODO: track field-level staleness
        "anomaly_flags": anomaly_flags,
    }


def _try_yfinance_merge(symbol: str, builder: FundametricsResponseBuilder, log) -> List[str]:
    """Attempt to merge yfinance financials to fill gaps. Returns list of data sources used."""
    extra_sources = []
    try:
        from scraper.sources.yfinance_source import get_raw_financials
        yf_data = get_raw_financials(symbol)
        if yf_data:
            builder.merge_with_yfinance(yf_data)
            extra_sources.append("yfinance_financials")
            log.info("yfinance financials merged", symbol=symbol)
    except Exception as exc:
        log.warning("yfinance merge skipped", symbol=symbol, error=str(exc))
    return extra_sources


def _try_nse_shareholding(symbol: str, log) -> Optional[Dict[str, Any]]:
    """Attempt to fetch shareholding from NSE as fallback."""
    try:
        from scraper.sources.nse_source import get_shareholding
        result = get_shareholding(symbol)
        if result and result.get("status") == "available":
            log.info("NSE shareholding fetched", symbol=symbol, status="available")
            return result
    except Exception as exc:
        log.warning("NSE shareholding fallback failed", symbol=symbol, error=str(exc))
    return None


def _try_twelvedata_fallback(symbol: str, completeness_score: float, log) -> Optional[Dict[str, Any]]:
    """Attempt Twelve Data if completeness is below 0.5."""
    if completeness_score >= 0.5:
        return None
    try:
        from scraper.sources.twelvedata_source import get_financials
        result = get_financials(symbol)
        if result and result.get("status") == "ok":
            log.info("Twelve Data fallback used", symbol=symbol, completeness=completeness_score)
            return result
    except Exception as exc:
        log.warning("Twelve Data fallback failed", symbol=symbol, error=str(exc))
    return None


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
    builder.set_canonical_financials(financials)

    quarters = financials.get("quarters")
    if quarters:
        builder.set_quarterly_financials(quarters)



    # ─── yfinance merge (Phase 3) ────────────────────────────────────
    extra_sources = _try_yfinance_merge(symbol, builder, log)

    # ─── Shareholding: Trendlyne -> NSE fallback (Phase 4) ───────────
    shareholding_block = clean_data.get("shareholding") if enable_shareholding else None
    if shareholding_block:
        builder.add_shareholding(shareholding_block)
    elif enable_shareholding:
        # Try NSE direct as fallback
        nse_shareholding = _try_nse_shareholding(symbol, log)
        if nse_shareholding and nse_shareholding.get("status") == "available":
            builder.add_shareholding(nse_shareholding.get("summary", {}))
            extra_sources.append("nse_shareholding")

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

    # ─── Completeness score + Quality report (Phase 8) ───────────────
    all_sources = builder.data_sources + extra_sources
    quality = _build_quality_report(response, all_sources)
    completeness_score = quality["completeness_score"]

    # ─── Twelve Data fallback if completeness < 0.5 (Phase 8) ────────
    td_data = _try_twelvedata_fallback(symbol, completeness_score, log)
    if td_data:
        extra_sources.append("twelvedata")
        # Recalculate quality
        quality = _build_quality_report(response, all_sources + ["twelvedata"])

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
        "data_completeness_score": quality["completeness_score"],
        "quality": quality,
    }

    if repository:
        repository.save_run(symbol=symbol, run_id=run_id, payload=run_payload)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol.lower()}_{timestamp}.json"
    output_path.write_text(json.dumps(response, indent=2), encoding="utf-8")

    log.success("Run completed", symbol=symbol, run_id=run_id, validation_status=validation_report.get("status"), completeness=quality["completeness_score"])
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
