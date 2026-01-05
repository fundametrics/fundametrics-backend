from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from scraper.api.settings import get_api_settings
from scraper.core.analytics.trends import TrendEngine
from scraper.core.config import Config
from scraper.core.fetcher import Fetcher
from scraper.core.health import build_health_snapshot
from scraper.core.ingestion import ingest_symbol
from scraper.core.market_facts_engine import MarketFactsEngine
from scraper.core.repository import DataRepository
from scraper.core.state import write_last_ingestion
from scraper.core.storage import write_company_snapshot
from scraper.core.validators import SymbolValidationError
from scraper.core.indices import INDEX_CONSTITUENTS, get_constituents

router = APIRouter()
repo = DataRepository()
trend_engine = TrendEngine(repo)
market_engine = MarketFactsEngine(Fetcher())


class IngestRequest(BaseModel):
    symbol: str
    force: bool = False


def require_ingest_access(request: Request, settings=Depends(get_api_settings)) -> None:
    if not settings.ingest_enabled:
        raise HTTPException(status_code=403, detail="Ingestion disabled")

    if settings.admin_api_key:
        api_key = request.headers.get("x-api-key")
        if api_key != settings.admin_api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/admin/ingest")
async def admin_ingest(payload: IngestRequest, _: None = Depends(require_ingest_access)):
    settings = get_api_settings()
    started_at = datetime.now(timezone.utc)
    run_context = {
        "run_id": f"manual-{started_at.strftime('%Y%m%dT%H%M%S')}",
        "started_at": started_at.isoformat(),
        "status": "failed",
        "symbols_processed": 0,
        "failures": [payload.symbol.upper()],
        "warnings": 0,
        "source": "manual",
        "symbols": [payload.symbol.upper()],
    }

    try:
        result = await ingest_symbol(payload.symbol, allowlist=settings.ingest_allowlist)
    except SymbolValidationError as exc:
        run_context["status"] = "failed"
        run_context["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_last_ingestion(run_context)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        run_context["status"] = "failed"
        run_context["finished_at"] = datetime.now(timezone.utc).isoformat()
        run_context["error"] = str(exc)
        write_last_ingestion(run_context)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    stored_at = write_company_snapshot(result["symbol"], result["storage_payload"])

    finished_at = datetime.now(timezone.utc)
    warnings = result.get("warnings", [])
    run_context.update(
        {
            "run_id": result["storage_payload"].get("run_id", run_context["run_id"]),
            "status": "success",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "symbols_processed": 1,
            "failures": [],
            "warnings": len(warnings),
            "source": "manual",
            "symbols": [result["symbol"]],
        }
    )
    write_last_ingestion(run_context)

    return {
        "symbol": result["symbol"],
        "status": "success",
        "blocks_ingested": result["blocks_ingested"],
        "warnings": warnings,
        "stored_at": stored_at,
    }


@router.get("/admin/health")
def admin_health(
    _: None = Depends(require_ingest_access),
    include_internal: bool = Query(False, alias="include_internal"),
):
    settings = get_api_settings()
    report = build_health_snapshot(settings, repo)

    payload = dict(report.public)
    if include_internal:
        payload["_internal"] = report.internal

    return payload


def _compute_coverage(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    blocks = {
        "company_profile": bool(payload.get("company")),
        "financials_snapshot": bool(payload.get("financials", {}).get("latest")),
        "financial_ratios": bool(payload.get("financials", {}).get("ratios")),
        "shareholding": bool(payload.get("shareholding", {}).get("summary")),
        "signals": bool(payload.get("signals")),
        "ai_summary": bool(payload.get("ai_summary", {}).get("paragraphs")),
        "metadata": bool(payload.get("metadata")),
    }

    available_blocks = [key for key, present in blocks.items() if present]
    missing_blocks = [key for key, present in blocks.items() if not present]
    coverage_score = round(len(available_blocks) / len(blocks), 2) if blocks else 0.0

    warnings: List[Dict[str, str]] = []
    if missing_blocks:
        warnings.append(
            {
                "code": "missing_blocks",
                "level": "info",
                "message": "The latest processed run did not include: "
                + ", ".join(sorted(missing_blocks)),
            }
        )

    coverage_payload = {
        "score": coverage_score,
        "available": available_blocks,
        "missing": missing_blocks,
        "note": "Coverage reflects factual data blocks present in the latest processed run. No qualitative judgment implied.",
    }

    return coverage_payload, warnings


def _reshape_for_frontend(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms the canonical Fundametrics response into the dense structure 
    expected by the Phase 20 Visual Intelligence UI.
    """
    # 1. Map Metrics to List (Deduplicated)
    # CRITICAL FIX: Metrics are nested under response['metrics']['values'] and response['metrics']['ratios']
    metrics_block = response.get("metrics", {})
    raw_metrics = metrics_block.get("values", {}) if isinstance(metrics_block, dict) else {}
    ratios = metrics_block.get("ratios", {}) if isinstance(metrics_block, dict) else {}
    
    # Combined metrics map to handle overlaps
    combined_metrics: Dict[str, Dict[str, Any]] = {}
    
    # Order matters: later ones overwrite earlier ones if name matches
    # We'll normalize names to deduplicate
    for source in [ratios, raw_metrics]:
        if not isinstance(source, dict):
            continue
        for key, data in source.items():
            if not isinstance(data, dict):
                continue
            
            display_name = key.replace("fundametrics_", "").replace("_", " ").title()
            
            # Handle Growth horizons for GrowthSummary.tsx matching
            if any(h in display_name for h in [" 10Y", " 5Y", " 3Y", " 1Y"]):
                display_name = display_name.replace(" 10Y", " (10Y)")\
                                         .replace(" 5Y", " (5Y)")\
                                         .replace(" 3Y", " (3Y)")\
                                         .replace(" 1Y", " (1Y)")

            # Special case mapping for consistency
            NAME_MAP = {
                "Net Profit Margin": "Net Margin",
                "Earnings Per Share": "Eps",
                "Price To Earnings": "Pe Ratio",
                "Operating Profit Margin": "Operating Margin",
                "Return On Equity": "ROE",
                "Roe (10Y)": "ROE (10Y)",
                "Roe (5Y)": "ROE (5Y)",
                "Roe (3Y)": "ROE (3Y)",
                "Profit Growth (10Y)": "Profit Growth (10Y)",
                "Profit Growth (5Y)": "Profit Growth (5Y)",
                "Profit Growth (3Y)": "Profit Growth (3Y)",
                "Profit Growth (1Y)": "Profit Growth (1Y)",
            }
            display_name = NAME_MAP.get(display_name, display_name)
            
            # If we already have this metric, only keep the one with a value
            if display_name in combined_metrics:
                if combined_metrics[display_name].get("value") is not None and data.get("value") is None:
                    continue
            
            # Determine drift flag
            drift = data.get("drift", {})
            if not isinstance(drift, dict):
                drift = {"drift_flag": "neutral", "z_score": 0, "magnitude": 0}

            # Extract and normalize confidence to 0-1 float
            raw_conf = data.get("confidence")
            conf_val = 0.0
            if isinstance(raw_conf, dict):
                conf_val = float(raw_conf.get("score", 0)) / 100.0
            elif isinstance(raw_conf, (int, float)):
                conf_val = float(raw_conf) / 100.0 if raw_conf > 1 else float(raw_conf)

            combined_metrics[display_name] = {
                "metric_name": display_name,
                "value": data.get("value"),
                "unit": data.get("unit", ""),
                "confidence": conf_val,
                "trust_score": raw_conf if isinstance(raw_conf, dict) else {"grade": "N/A", "score": 0},
                "reason": data.get("reason"),
                "drift": drift,
                "integrity": data.get("integrity", "unverified"),
                "explainability": data.get("explainability", {"formula": "Internal Computation", "inputs": []})
            }
    
    # Prioritized sorting for the dashboard
    PRIORITY = [
        "Pe Ratio",
        "Return On Equity",
        "Debt To Equity",
        "Eps",
        "Book Value Per Share",
        "Price To Book",
        "Operating Margin",
        "Net Margin",
        "Interest Coverage",
        "Asset Turnover"
    ]
    
    sorted_metrics = []
    # First, add prioritized ones if they exist
    for p_name in PRIORITY:
        if p_name in combined_metrics:
            sorted_metrics.append(combined_metrics.pop(p_name))
    
    # Then add the rest
    remaining = list(combined_metrics.values())
    remaining.sort(key=lambda x: x["metric_name"])
    sorted_metrics.extend(remaining)
    
    response["fundametrics_metrics"] = sorted_metrics

    # 2. Map Yearly Financials for Charts
    yearly_financials: Dict[str, List[Dict[str, Any]]] = {}
    
    # Mapping from Raw/Internal Labels to Frontend Chart & Table Keys
    CHART_MAP = {
        "Sales": "revenue",
        "revenue": "revenue",
        "Net Profit": "net_income",
        "net_income": "net_income",
        "Operating Profit": "operating_profit",
        "operating_profit": "operating_profit",
        "OPM %": "operating_profit_margin",
        "operating_profit_margin": "operating_profit_margin",
        "Reserves": "reserves",
        "reserves": "reserves",
        "Borrowings": "borrowings",
        "borrowings": "borrowings",
        "ROE %": "roe",
        "roe": "roe",
        "ROCE %": "roce",
        "roce": "roce",
        "EPS in Rs": "eps",
        "eps": "eps",
        "Profit before tax": "profit_before_tax",
        "profit_before_tax": "profit_before_tax",
        "Tax %": "tax_pct",
        "tax_pct": "tax_pct",
        "Dividend Payout %": "dividend_payout_pct",
        "Other Income": "other_income",
        "other_income": "other_income",
        "Interest": "interest",
        "interest": "interest",
        "Depreciation": "depreciation",
        "depreciation": "depreciation",
        "expenses": "expenses",
        "Expenses": "expenses",
        "net_profit_margin": "net_profit_margin",
        "Equity Capital": "equity_capital",
        "equity_capital": "equity_capital",
        "Total Liabilities": "total_liabilities",
        "total_liabilities": "total_liabilities",
        "Fixed Assets": "fixed_assets",
        "fixed_assets": "fixed_assets",
        "CWIP": "cwip",
        "cwip": "cwip",
        "Investments": "investments",
        "investments": "investments",
        "Other Assets": "other_assets",
        "other_assets": "other_assets",
        "Total Assets": "total_assets",
        "total_assets": "total_assets",
        "Cash from Operating Activity": "cash_flow_operating",
        "cash_flow_operating": "cash_flow_operating",
        "Cash from Investing Activity": "cash_flow_investing",
        "cash_flow_investing": "cash_flow_investing",
        "Cash from Financing Activity": "cash_flow_financing",
        "cash_flow_financing": "cash_flow_financing",
        "Net Cash Flow": "net_cash_flow",
        "net_cash_flow": "net_cash_flow",
        "Book Value": "book_value",
        "book_value": "book_value",
        "Price to Earnings": "pe_ratio",
        "price_to_earnings": "pe_ratio",
        "pe_ratio": "pe_ratio",
        "Dividend Yield": "dividend_yield",
        "Dividend Yield %": "dividend_yield",
        "dividend_yield": "dividend_yield",
        "Face Value": "face_value",
        "face_value": "face_value"
    }
    
    financials_block = response.get("financials", {})
    stmt_types = ["income_statement", "balance_sheet", "cash_flow", "ratios_table"]
    
    seen_points: Dict[str, Dict[str, Any]] = {}

    for stmt_type in stmt_types:
        stmt = financials_block.get(stmt_type, {})
        if not isinstance(stmt, dict):
            continue
            
        for period, row in stmt.items():
            if not isinstance(row, dict):
                continue
            for metric, data in row.items():
                val = data.get("value") if isinstance(data, dict) else data
                if val is None:
                    continue
                
                target_key = CHART_MAP.get(metric, metric)
                
                if target_key not in seen_points:
                    seen_points[target_key] = {}
                
                # Keep first non-null value for each period/target pair
                if period not in seen_points[target_key]:
                    seen_points[target_key][period] = val

    # Convert results into the list format expected by the frontend
    for m_key, points in seen_points.items():
        yearly_financials[m_key] = [
            {"period": p, "value": v} for p, v in points.items()
        ]
        
        def _sort_key(p_dict):
            p = p_dict["period"]
            if p == "TTM":
                return "9999-12-31"
            try:
                # Handle 'Mar 2024'
                parts = p.split()
                if len(parts) == 2:
                    month_map = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", 
                                "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
                    return f"{parts[1]}-{month_map.get(parts[0], '00')}-01"
            except: pass
            return p

        yearly_financials[m_key].sort(key=_sort_key)

    response["yearly_financials"] = yearly_financials
    response.setdefault("management", [])
    
    return response


def _prepare_company_payload(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    response = deepcopy(raw_data.get("fundametrics_response", {}))

    metadata = response.setdefault("metadata", {})
    raw_shareholding = raw_data.get("shareholding", {})

    raw_status = metadata.get("shareholding_status") or raw_shareholding.get("status")
    status_map = {
        "available": "available",
        "ok": "available",
        "unavailable": "unavailable",
        "partial": "partial",
    }
    status = status_map.get((raw_status or "").lower(), "unavailable")

    # Preserve rich shareholding from api_response_builder if modern structure present
    if "shareholding" in response and isinstance(response["shareholding"], dict) and response["shareholding"].get("history"):
        # Already correctly structured by api_response_builder.py
        pass
    else:
        insights = response.pop("shareholding_insights", None)
        summary = response.pop("shareholding_summary", None)
        history = response.pop("shareholding_history", None)

        if status != "available":
            insights = None

        response["shareholding"] = {
            "status": status,
            "summary": summary,
            "insights": insights,
            "history": history,
        }

    coverage, warnings = _compute_coverage(response)

    metadata.setdefault("run_id", raw_data.get("run_id"))
    metadata.setdefault("run_timestamp", raw_data.get("run_timestamp"))
    metadata["warnings"] = warnings
    metadata["disclaimer"] = (
        "Fundametrics coverage indicates which disclosures were processed in the latest run. "
        "It is informational only and does not reflect performance, suitability, or recommendations."
    )

    response["coverage"] = coverage

    # Phase 20 Visual Reshaping
    response = _reshape_for_frontend(response)

    return response


@router.get("/stocks/{symbol}")
def get_latest_stock(symbol: str):
    data = repo.get_latest(symbol)
    if not data:
        raise HTTPException(status_code=404, detail="Symbol not found")

    return _prepare_company_payload(data)


@router.get("/search")
def search_symbols(
    q: str = Query("", alias="query"),
    sector: Optional[str] = Query(None)
):
    """Informational search across processed company runs."""
    query = (q or "").strip().lower()

    try:
        symbols = repo.list_symbols()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list symbols: {exc}")

    results: List[Dict[str, str]] = []
    disclaimer = (
        "Search results are informational only, based on previously processed disclosures. "
        "They do not constitute investment advice or recommendations."
    )

    if not symbols:
        return {"query": q, "results": results, "disclaimer": disclaimer}

    sector_filter = sector.lower() if sector else None

    for symbol in sorted(symbols):
        payload = repo.get_latest(symbol)
        if not payload:
            continue

        company_block = payload.get("fundametrics_response", {}).get("company", {})
        name = company_block.get("name")
        sector_val = company_block.get("sector")

        if not name:
            continue

        if query and query not in symbol.lower() and query not in name.lower() and (
            not sector_val or query not in sector_val.lower()
        ):
            continue

        if sector_filter and (not sector_val or sector_filter != sector_val.lower()):
            continue

        results.append(
            {
                "symbol": symbol.upper(),
                "name": name,
                "sector": sector or "Not disclosed",
            }
        )

        if len(results) >= 25:
            break

    return {"query": q, "results": results, "disclaimer": disclaimer}


@router.get("/stocks")
def list_stocks():
    try:
        symbols = repo.list_symbols()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list symbols: {exc}")

    ordered_symbols = sorted(sym.upper() for sym in symbols)

    return {
        "count": len(ordered_symbols),
        "symbols": ordered_symbols,
    }


@router.get("/coverage")
def list_coverage():
    try:
        symbols = repo.list_symbols()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list symbols: {exc}")

    records = []
    block_totals: Dict[str, int] = {}

    for symbol in symbols:
        raw = repo.get_latest(symbol)
        if not raw:
            continue

        payload = _prepare_company_payload(raw)
        coverage = payload.get("coverage", {})
        metadata = payload.get("metadata", {})

        for block in coverage.get("available", []):
            block_totals[block] = block_totals.get(block, 0) + 1

        records.append(
            {
                "symbol": symbol.upper(),
                "name": payload.get("company", {}).get("name"),
                "sector": payload.get("company", {}).get("sector"),
                "coverage": coverage,
                "last_processed": metadata.get("run_timestamp") or raw.get("run_timestamp"),
                "warnings": metadata.get("warnings", []),
            }
        )

    response_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "symbols": len(records),
            "block_availability": block_totals,
        },
        "results": records,
        "disclaimer": "Coverage summarises data availability only. It is not indicative of performance or recommendations.",
    }

    return response_payload


@router.get("/stocks/{symbol}/runs")
def list_stock_runs(symbol: str):
    runs = repo.list_runs(symbol)
    if not runs:
        raise HTTPException(status_code=404, detail="No runs found for symbol")
    return runs


@router.get("/stocks/{symbol}/market")
async def get_market_facts(symbol: str):
    """
    Read-only market facts for a symbol.
    Returns delayed price, 52-week range, shares outstanding, and computed market cap.
    No advisory or predictive information - factual data only with explicit delay and disclaimer.
    """
    try:
        market_facts = await market_engine.fetch_market_facts(symbol.upper())
        market_block = market_engine.build_market_block(market_facts)
        
        # Ensure API contract - only factual data with explicit metadata
        response = {
            "symbol": symbol.upper(),
            "market": market_block,
            "api_contract": {
                "data_type": "facts_only",
                "no_advisory_content": True,
                "delay_disclosed": True,
                "disclaimer_included": True,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        }
        
        return response
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market facts: {str(exc)}")


@router.get("/api/v1/symbol/{symbol}/trends")
def get_symbol_trends(symbol: str, periods: int = 4):
    """
    Read-only historical trend analytics for a symbol.
    Computes revenue CAGR, promoter trend, signal momentum, and stability.
    """
    if periods < 2 or periods > 12:
        raise HTTPException(status_code=400, detail="periods must be between 2 and 12")
    # Ensure we have at least one run for the symbol
    if not repo.get_latest(symbol):
        raise HTTPException(status_code=404, detail="Symbol not found")
    trends = trend_engine.compute(symbol, periods=periods)
    # Sanitize to public response shape
    payload = {
        "symbol": trends.get("symbol"),
        "computed_at": trends.get("computed_at"),
        "periods_analyzed": trends.get("periods_analyzed"),
        "revenue_trend": trends.get("revenue", {}).get("trend"),
        "promoter_trend": trends.get("promoter", {}).get("trend"),
        "signal_momentum": trends.get("signal_momentum"),
        "stability_score": trends.get("stability_score"),
    }
    if "error" in trends:
        payload["error"] = trends["error"]
    return payload
@router.get("/indices")
def get_available_indices():
    """List all available indices."""
    return list(INDEX_CONSTITUENTS.keys())


@router.get("/indices/{index_name}/constituents")
def get_index_constituents(index_name: str):
    """Get constituent symbols and basic metadata for an index."""
    symbols = get_constituents(index_name)
    if not symbols:
        raise HTTPException(status_code=404, detail=f"Index {index_name} not found")
    
    # Enrich with basic info if available in repo
    enriched = []
    for sym in symbols:
        try:
            # We just return the symbol and name for now
            # If we had a fast way to get names for all, we'd use it
            # For now, just symbol as fallback name
            enriched.append({
                "symbol": sym,
                "name": sym, # Fallback
                "sector": "Market Weighted"
            })
        except:
            continue
            
    return {
        "index": index_name.upper(),
        "count": len(enriched),
        "constituents": enriched
    }


@router.get("/sectors")
def get_all_sectors():
    """List all unique sectors available in the repository."""
    symbols = repo.list_symbols()
    sectors = set()
    for symbol in symbols:
        payload = repo.get_latest(symbol)
        if payload:
            s = payload.get("fundametrics_response", {}).get("company", {}).get("sector")
            if s:
                sectors.add(s)
    return sorted(list(sectors))
