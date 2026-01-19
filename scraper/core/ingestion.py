"""Ingestion orchestration for on-demand symbol processing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple
from uuid import uuid4

from scraper.core.api_response_builder import FundametricsResponseBuilder
from scraper.core.data_pipeline import DataPipeline
from scraper.core.fetcher import Fetcher
from scraper.core.market_facts_engine import MarketFactsEngine
from scraper.sources.screener import ScreenerScraper
from scraper.sources.trendlyne import TrendlyneScraper
from scraper.sources.news_scraper import NewsScraper
from scraper.utils.logger import get_logger
from scraper.core.trust_report import build_trust_report
from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_db

log = get_logger(__name__)


async def _fetch_financials(symbol: str, fetcher: Fetcher) -> Dict[str, Any]:
    screener = ScreenerScraper(fetcher)
    return await screener.scrape_stock(symbol)


async def _fetch_profile(symbol: str, fetcher: Fetcher) -> Dict[str, Any]:
    trendlyne = TrendlyneScraper(fetcher)
    return await trendlyne.scrape_stock(symbol)


async def _fetch_market(symbol: str, fetcher: Fetcher) -> Dict[str, Any]:
    engine = MarketFactsEngine(fetcher)
    market = await engine.fetch_market_facts(symbol)
    return engine.build_market_block(market)


async def _fetch_news(symbol: str, company_name: str, fetcher: Fetcher) -> List[Dict[str, Any]]:
    scraper = NewsScraper(fetcher)
    return await scraper.fetch_news(symbol, company_name)


def _merge_metadata(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = base.copy()
    for k, v in extra.items():
        if v is not None:
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
    return merged


def _make_warning(code: str, message: str, *, level: str = "info") -> Dict[str, str]:
    return {
        "code": code,
        "level": level,
        "message": message,
    }


def _build_fundametrics_response(symbol: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, str]]]:
    log.debug(f"Building fundametrics response... {symbol}")
    if "constants" in payload.get("metadata", {}):
        log.debug(f"Constants present in payload: {payload['metadata']['constants']}")
    
    pipeline = DataPipeline()
    pipeline_result = pipeline.process(payload)
    clean_data = pipeline_result.get("clean_data", {}) or {}
    validation_report = pipeline_result.get("validation_report", {}) or {}

    builder = FundametricsResponseBuilder(
        symbol=symbol,
        company_name=clean_data.get("metadata", {}).get("company_name") or payload["metadata"].get("company_name") or symbol,
        sector=clean_data.get("metadata", {}).get("sector") or payload["metadata"].get("sector") or "Unknown",
    )

    builder.set_company_metadata(clean_data.get("metadata"))
    builder.set_market_facts(payload.get("market"))
    
    # Extract About and Management profiles
    metadata = clean_data.get("metadata", {})
    if metadata.get("about"):
        builder.set_about(metadata["about"])
    
    # Combine management and executives if both present
    mgmt = metadata.get("management", [])
    execs = metadata.get("executives", [])
    combined_mgmt = mgmt + execs
    if combined_mgmt:
        builder.set_management(combined_mgmt)

    canonical_financials = clean_data.get("canonical_financials")
    if canonical_financials:
        builder.set_canonical_financials(canonical_financials)
        if canonical_financials.get("meta", {}).get("periods"):
            builder.set_quarterly_financials(canonical_financials["meta"].get("periods"))
    else:
        financials = clean_data.get("financials", {}) or {}
        if financials.get("quarters"):
            builder.set_quarterly_financials(financials["quarters"])

    shareholding_block = clean_data.get("shareholding")
    if shareholding_block:
        builder.add_shareholding(shareholding_block)

    news = payload.get("news")
    if news:
        builder.set_news(news)

    response = builder.build()
    response.setdefault("metadata", {})
    response["metadata"]["validation_status"] = validation_report.get("status")
    response["metadata"]["warnings"] = [
        issue for issue in validation_report.get("issues", []) if issue.get("level") != "error"
    ]

    run_timestamp = datetime.now(timezone.utc).isoformat()
    response["metadata"]["run_timestamp"] = run_timestamp

    coverage_map = {
        "company_profile": bool(response.get("company")),
        "financials_snapshot": bool(response.get("financials", {}).get("latest")),
        "financial_ratios": bool(response.get("financials", {}).get("ratios")),
        "shareholding": bool(response.get("shareholding", {}).get("summary")),
        "signals": bool(response.get("signals")),
        "ai_summary": bool(response.get("ai_summary", {}).get("paragraphs")),
        "news": bool(response.get("news")),
        "metadata": bool(response.get("metadata")),
    }

    available_blocks = [key for key, present in coverage_map.items() if present]
    missing_blocks = [key for key, present in coverage_map.items() if not present]
    coverage_score = round(len(available_blocks) / len(coverage_map), 2) if coverage_map else 0.0

    coverage_payload = {
        "score": coverage_score,
        "available": available_blocks,
        "missing": missing_blocks,
        "note": "Coverage reflects factual data blocks present in the latest run. No qualitative judgement implied.",
    }

    coverage_warnings: List[Dict[str, str]] = []
    if missing_blocks:
        coverage_warnings.append(
            _make_warning(
                "missing_blocks",
                "The latest ingestion did not include: " + ", ".join(sorted(missing_blocks)),
            )
        )

    response["coverage"] = coverage_payload
    response["metadata"].setdefault("warnings", []).extend(coverage_warnings)

    return response, coverage_payload, coverage_warnings


async def ingest_symbol(symbol: str, *, allowlist: Iterable[str] | None = None) -> Dict[str, Any]:
    """Orchestrate the ingestion flow for a single symbol."""

    normalised_symbol = symbol.strip().upper()

    log.info("Beginning ingestion for {}", normalised_symbol)

    ingest_started = datetime.now(timezone.utc)

    from scraper.core.rate_limiters import yahoo_limiter, screener_limiter, trendlyne_limiter
    
    # We use specialized fetchers for each source to respect their specific limits
    yahoo_fetcher = Fetcher(rate_limiter=yahoo_limiter)
    screener_fetcher = Fetcher(rate_limiter=screener_limiter)
    trendlyne_fetcher = Fetcher(rate_limiter=trendlyne_limiter)
    news_fetcher = Fetcher(rate_limiter=yahoo_limiter) # News also from Yahoo/Google
    
    try:
        tasks = {
            "financials": _fetch_financials(normalised_symbol, screener_fetcher),
            "profile": _fetch_profile(normalised_symbol, trendlyne_fetcher),
            "market": _fetch_market(normalised_symbol, yahoo_fetcher),
            "news": _fetch_news(normalised_symbol, normalised_symbol, news_fetcher),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        raw_blocks = dict(zip(tasks.keys(), results))
    finally:
        await asyncio.gather(
            yahoo_fetcher.close(),
            screener_fetcher.close(),
            trendlyne_fetcher.close(),
            news_fetcher.close()
        )

    warnings: List[Dict[str, str]] = []
    payload: Dict[str, Any] = {
        "symbol": normalised_symbol,
        "metadata": {"company_name": normalised_symbol},
        "financials": {},
        "shareholding": None,
        "market": None,
        "news": [],
    }
    # Handle fetch failures explicitly to produce accurate warning severities
    fetch_failures = {}
    for block, result in raw_blocks.items():
        if isinstance(result, Exception):
            fetch_failures[block] = result
            raw_blocks[block] = None
            log.error("Failed to fetch %s block for %s: %s", block, normalised_symbol, result)

    financials = raw_blocks.get("financials")
    if isinstance(financials, dict) and financials:
        payload["financials"] = financials.get("financials", {})
        payload["shareholding"] = financials.get("shareholding")
        payload["metadata"] = _merge_metadata(payload["metadata"], financials.get("metadata", {}))
    else:
        if "financials" in fetch_failures:
            warnings.append(
                _make_warning(
                    "financials_fetch_failed",
                    "Financial disclosures request failed during ingestion.",
                    level="critical",
                )
            )
        else:
            warnings.append(
                _make_warning(
                    "financials_unavailable",
                    "Financial disclosures could not be retrieved during ingestion.",
                    level="warning",
                )
            )

    profile = raw_blocks.get("profile")
    if isinstance(profile, dict) and profile:
        payload["metadata"] = _merge_metadata(payload["metadata"], profile)
        payload.setdefault("company", {})["about"] = profile.get("about")
    else:
        if "profile" in fetch_failures:
            warnings.append(
                _make_warning(
                    "profile_fetch_failed",
                    "Company profile request failed during ingestion.",
                    level="critical",
                )
            )
        else:
            warnings.append(
                _make_warning(
                    "profile_unavailable",
                    "Company profile information was unavailable from the source.",
                )
            )

    market = raw_blocks.get("market")
    if isinstance(market, dict) and market:
        payload["market"] = market
    else:
        if "market" in fetch_failures:
            warnings.append(
                _make_warning(
                    "market_fetch_failed",
                    "Delayed market facts request failed during ingestion.",
                    level="critical",
                )
            )
        else:
            warnings.append(
                _make_warning(
                    "market_unavailable",
                    "Delayed market facts could not be fetched for this symbol.",
                )
            )

    news = raw_blocks.get("news")
    if isinstance(news, list) and news:
        payload["news"] = news

    metadata = payload.setdefault("metadata", {})
    metadata.update(
        {
            "generated": ingest_started.isoformat(),
            "mode": "historical",
            "advisory": False,
            "as_of": ingest_started.isoformat(),
            "sources": [key for key, value in raw_blocks.items() if isinstance(value, dict) and value],
            "ttl_hours": metadata.get("ttl_hours", 24),
        }
    )

    response, coverage_payload, coverage_warnings = _build_fundametrics_response(normalised_symbol, payload)
    response_metadata = response.setdefault("metadata", {})
    response_metadata.setdefault("generated", metadata.get("generated", response_metadata.get("run_timestamp")))
    response_metadata.setdefault("ttl_hours", metadata.get("ttl_hours", 24))

    metadata_warnings = metadata.setdefault("warnings", [])
    metadata_warnings.extend(warnings)
    metadata_warnings.extend(coverage_warnings)

    # Phase 24: Persist Trust Report
    run_id = f"ingest-{uuid4()}"
    
    trust_report = build_trust_report(
        symbol=normalised_symbol,
        run_id=run_id,
        coverage=coverage_payload,
        warnings=metadata_warnings
    )
    
    # Optional: Persist to MongoDB if repository is available
    try:
        repo = MongoRepository(get_db())
        await repo.upsert_trust_report(trust_report)
    except Exception as e:
        log.warning(f"Could not persist trust report to MongoDB: {e}")

    run_timestamp = response_metadata.get("run_timestamp", datetime.now(timezone.utc).isoformat())
    response_metadata["run_id"] = run_id

    log.info("Ingestion completed for %s", normalised_symbol)

    storage_payload = {
        "symbol": normalised_symbol,
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "validation": {"status": response_metadata.get("validation_status")},
        "warnings": metadata_warnings,
        "fundametrics_response": response,
        "shareholding": response.get("shareholding"),
        "meta": {
            "generated": response_metadata.get("generated", run_timestamp),
            "ttl_hours": response_metadata.get("ttl_hours", 24),
        },
    }

    return {
        "symbol": normalised_symbol,
        "payload": response,
        "storage_payload": storage_payload,
        "warnings": metadata_warnings,
        "blocks_ingested": coverage_payload.get("available", []),
    }


__all__ = ["ingest_symbol"]
