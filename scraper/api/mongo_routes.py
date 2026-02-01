"""
MongoDB-based API Routes - Phase 22

This module provides API endpoints that use MongoDB instead of SQLite.
Start with /stocks/{symbol} for RELIANCE as proof of concept.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, timezone
import os
import logging
import asyncio

from scraper.core.db import get_client, get_db, get_companies_col, get_mongo_uri

# Initialize indices for first run
from scraper.core.indices import INDEX_CONSTITUENTS, get_constituents, YAHOO_INDEX_MAP
from scraper.core.fetcher import Fetcher
from scraper.core.mongo_repository import MongoRepository
from scraper.core.market_facts_engine import MarketFactsEngine
from scraper.core.rate_limiters import yahoo_limiter
from scraper.utils.yahoo_session import YahooSession
fetcher = Fetcher(rate_limiter=yahoo_limiter, max_retries=1)
market_engine = MarketFactsEngine(fetcher=fetcher)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
class LazyMongoRepository:
    """Proxy that initializes MongoRepository on first access to prevent boot crashes"""
    _instance = None
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = MongoRepository(get_db())
        return getattr(self._instance, name)

mongo_repo = LazyMongoRepository()
# Simple TTL Cache for /companies (Phase 5)
_COMPANIES_CACHE = {"data": None, "timestamp": 0}
CACHE_TTL_SECONDS = 300 # 5 minutes


@router.get("/companies")
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("symbol"),
    order: int = Query(1, description="1 for ASC, -1 for DESC"),
    sector: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search query for symbol or name"),
    backfill: Optional[bool] = Query(False),
    min_market_cap: Optional[float] = Query(None),
    max_market_cap: Optional[float] = Query(None),
    min_pe: Optional[float] = Query(None),
    max_pe: Optional[float] = Query(None),
    min_roe: Optional[float] = Query(None)
):
    """
    Get list of companies with basic info (Phase 23)
    Supports pagination, server-side sorting, and advanced filtering (Phase 5/6).
    """
    # Cache key for this specific query - must include ALL filters to prevent pollution
    cache_key = f"{skip}:{limit}:{sort_by}:{order}:{sector}:{q}:{min_market_cap}:{max_market_cap}:{min_pe}:{max_pe}:{min_roe}"
    
    # Check global cache if default view
    if skip == 0 and limit == 50 and sort_by == "symbol" and order == 1 and not any([sector, q, min_market_cap, max_market_cap, min_pe, max_pe, min_roe]):
        now = datetime.now().timestamp()
        if _COMPANIES_CACHE["data"] and (now - _COMPANIES_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _COMPANIES_CACHE["data"]
            
    try:
        if backfill:
            await mongo_repo.run_backfill()
            
        companies = await mongo_repo.get_all_companies(
            skip=skip, 
            limit=limit, 
            sort_by=sort_by, 
            order=order,
            sector=sector,
            q=q,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            min_pe=min_pe,
            max_pe=max_pe,
            min_roe=min_roe
        )
        
        # Get accurate total count for filtered results
        if any([sector, q, min_market_cap, max_market_cap, min_pe, max_pe, min_roe]):
            total = await mongo_repo.count_companies(
                sector=sector,
                q=q,
                min_market_cap=min_market_cap,
                max_market_cap=max_market_cap,
                min_pe=min_pe,
                max_pe=max_pe,
                min_roe=min_roe
            )
        else:
            col = get_companies_col()
            total = await col.count_documents({"symbol": {"$not": {"$regex": "^--"}}})
             
        response = {
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(companies),
            "companies": companies
        }
        
        # Save to cache if it's the default view and NO filters are applied
        if skip == 0 and limit == 50 and sort_by == "symbol" and order == 1 and not any([sector, q, min_market_cap, max_market_cap, min_pe, max_pe, min_roe]):
            _COMPANIES_CACHE["data"] = response
            _COMPANIES_CACHE["timestamp"] = datetime.now().timestamp()
            
        return response
    except Exception as e:
        logging.error(f"Error fetching companies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch companies from database")


@router.get("/system/backfill")
async def trigger_backfill():
    """
    Administrative endpoint to promotoe nested data to root.
    Fixes filtering issues for legacy companies.
    """
    try:
        results = await mongo_repo.run_backfill()
        return {
            "status": "success",
            "message": "Global backfill completed successfully",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backfill failed: {str(e)}")


@router.get("/stocks")
async def list_stocks():
    """
    Get all company symbols (Legacy/Simple)
    """
    try:
        symbols = await mongo_repo.get_all_symbols()
        return {
            "count": len(symbols),
            "symbols": symbols
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch symbols: {str(e)}")


@router.get("/company/{symbol}")
@router.get("/stocks/{symbol}")
@limiter.limit("30/minute")
async def get_stock_detail(symbol: str, request: Request):
    """
    Get complete company data from MongoDB
    
    This endpoint fetches:
    - Company profile
    - Annual financials (all years)
    - Computed metrics
    - Ownership data
    - Trust metadata
    
    Returns Phase 20 UI-compatible response
    """
    symbol = symbol.upper()
    
    try:
        # 1. Get company profile
        company = await mongo_repo.get_company(symbol)
        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"Company {symbol} not found in database. Please ingest it first."
            )
        
        import asyncio
        
        # 2. Get financials and metrics concurrently
        income_task = mongo_repo.get_financials_annual(symbol, "income_statement")
        balance_task = mongo_repo.get_financials_annual(symbol, "balance_sheet")
        cash_task = mongo_repo.get_financials_annual(symbol, "cash_flow")
        metrics_task = mongo_repo.get_metrics(symbol)
        ownership_task = mongo_repo.get_ownership(symbol)
        
        # Optimize: Don't wait for live market facts in the main call.
        # The frontend fetches detailed market facts separately.
        # We perform MongoDB lookups only for maximum speed (~20ms).
        results = await asyncio.gather(
            income_task, balance_task, cash_task, metrics_task, ownership_task
        )
        
        income_statements, balance_sheets, cash_flows, metrics, ownership = results
        
        # Use simple fallback market block (no external call)
        live_market = {
             "price": {"value": None, "currency": "INR"}, 
             "metadata": {"source": "db_fallback", "data_type": "historical"}
        }

        # Fallback: Extract from stored blob if normalized collections are empty
        fundametrics_response = company.get("fundametrics_response", {})
        if not income_statements and "financials" in fundametrics_response:
             # Basic extraction
             pass
        
        if fundametrics_response and (not income_statements and not metrics):
             # Fast path: Transform the stored Fundametrics Response blob to UI structure
             trust_report = await mongo_repo.get_trust_report(symbol)
             return _transform_fundametrics_response(symbol, company, fundametrics_response, trust_report, live_market=live_market)

        # 4.5 Get trust report (Phase 24)
        trust_report = await mongo_repo.get_trust_report(symbol)

        # 5. Build Phase 20 UI response
        response = _build_ui_response(
            company=company,
            income_statements=income_statements,
            balance_sheets=balance_sheets,
            cash_flows=cash_flows,
            metrics=metrics,
            ownership=ownership,
            trust_report=trust_report,
            live_market=live_market
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch company data: {str(e)}")


@router.get("/peers/{symbol}")
async def get_peers(symbol: str):
    """
    Get peer companies in the same sector
    """
    try:
        mongo_repo = MongoRepository(get_db())
        peers = await mongo_repo.get_peers(symbol)
        return {"symbol": symbol, "peers": peers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch peers: {str(e)}")


@router.get("/search")
@limiter.limit("30/minute")
async def search_companies(
    request: Request,
    q: Optional[str] = Query(None),
    query: Optional[str] = Query(None)
):
    """
    Search companies by name or symbol
    """
    search_term = q or query or ""
    
    if not search_term.strip():
        return {
            "query": "",
            "results": [],
            "disclaimer": "Search results are informational only."
        }
    
    try:
        db = get_db()
        registry_col = db["companies_registry"]
        companies_col = db["companies"]
        
        search_regex = {"$regex": search_term.strip(), "$options": "i"}
        registry_results = await registry_col.find(
            {
                "$or": [
                    {"symbol": search_regex},
                    {"name": search_regex}
                ]
            },
            {"_id": 0, "symbol": 1, "name": 1, "sector": 1}
        ).limit(100).to_list(length=100)
        
        # Enrichment: Get accurate sectors for analyzed companies
        analyzed_cursor = companies_col.find({}, {"symbol": 1, "sector": 1, "fundametrics_response.company.sector": 1, "_id": 0})
        analyzed_sectors = {}
        async for doc in analyzed_cursor:
            sym = doc.get("symbol")
            if not sym: continue
            s = doc.get("sector")
            if not s or s == "Unknown":
                s = doc.get("fundametrics_response", {}).get("company", {}).get("sector") or "General"
            analyzed_sectors[sym] = s
        
        unique_results = {}
        for c in registry_results:
            symbol = c["symbol"]
            raw_name = c.get("name", "")
            norm_name = raw_name.lower().replace(".", "").replace(",", "").replace(" limited", "").replace(" ltd", "").replace(" (india)", "").strip()
            
            is_avail = symbol in analyzed_sectors
            status = "available" if is_avail else "not_available"
            
            # Prefer analyzed sector
            sector = analyzed_sectors.get(symbol) or c.get("sector", "General")
            if not sector or sector == "Unknown":
                sector = "General"
            
            candidate = {
                "symbol": symbol,
                "name": c.get("name"),
                "sector": sector,
                "status": status
            }
            
            if norm_name not in unique_results:
                unique_results[norm_name] = candidate
            else:
                if unique_results[norm_name]["status"] == "not_available" and status == "available":
                    unique_results[norm_name] = candidate

        results = list(unique_results.values())
        results.sort(key=lambda x: (x["status"] != "available", x["name"]))
        results = results[:50]
        
        return {
            "query": search_term,
            "results": results,
            "disclaimer": "Search results are informational only and do not constitute investment advice."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _transform_fundametrics_response(symbol: str, company: Dict, fr: Dict, trust_report: Optional[Dict] = None, live_market: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Transform the internal Fundametrics Response blob (from ResponseBuilder) 
    into the UI-compatible structure expected by the Phase 20/23 Frontend.
    """
    # 1. Map Metrics to List (Deduplicated & Normalized)
    metrics_block = fr.get("metrics", {})
    raw_metrics = metrics_block.get("values", {})
    ratios = metrics_block.get("ratios", {})
    
    combined_metrics: Dict[str, Dict[str, Any]] = {}

    def _normalize_name(name: str) -> str:
        # Clean: remove prefix, replace _ with space, title case
        n = name.replace("fundametrics_", "").replace("_", " ").title()
        
        # Hard-coded maps for frontend consistency
        NAME_MAP = {
            "Net Profit Margin": "Net Margin",
            "Earnings Per Share": "Eps",
            "Price To Earnings": "PE Ratio",
            "Pe Ratio": "PE Ratio",
            "Roe": "ROE",
            "Roce": "ROCE",
            "Eps": "EPS",
            "Operating Profit Margin": "Operating Margin",
            "Market Cap": "Market Cap",
            "Debt To Equity": "Debt To Equity"
        }
        return NAME_MAP.get(n, n)
    
    for source in [ratios, raw_metrics]:
        if not isinstance(source, dict): continue
        for key, data in source.items():
            if not isinstance(data, dict): continue
            
            display_name = _normalize_name(key)
            
            # Extract confidence and trust score
            raw_conf = data.get("confidence", {})
            conf_val = 0.0
            if isinstance(raw_conf, dict):
                conf_val = float(raw_conf.get("score", 0)) / 100.0
            
            combined_metrics[display_name] = {
                "metric_name": display_name,
                "value": data.get("value"),
                "unit": data.get("unit", ""),
                "confidence": conf_val,
                "trust_score": raw_conf if isinstance(raw_conf, dict) else {"grade": "N/A", "score": 0},
                "drift": data.get("drift", {"drift_flag": "neutral"}),
                "explainability": data.get("explainability", {"formula": "Computed from disclosures"})
            }
            
    # Merge with existing list if present (Critical for Fallback/Ingested data)
    existing_list = fr.get("fundametrics_metrics", [])
    if existing_list:
        for m in existing_list:
            if isinstance(m, dict) and m.get("metric_name"):
                name = _normalize_name(m["metric_name"])
                if name not in combined_metrics:
                    m_copy = m.copy()
                    m_copy["metric_name"] = name
                    combined_metrics[name] = m_copy

    fundametrics_metrics = list(combined_metrics.values())
    
    # Inject live price into the metrics list
    price_val = None
    if live_market and live_market.get("price") and live_market["price"].get("value"):
        price_val = live_market["price"]["value"]
        
    if price_val is not None:
        # Check if already in the list
        found = False
        for m in fundametrics_metrics:
            if m["metric_name"] == "Current Price":
                m["value"] = price_val
                found = True
                break
        
        if not found:
            fundametrics_metrics.insert(0, {
                "metric_name": "Current Price",
                "value": price_val,
                "unit": "INR",
                "confidence": 0.95,
                "trust_score": {"grade": "A", "score": 95},
                "drift": {"flag": "neutral"},
                "explainability": {"formula": "Latest market price"}
            })

    # 2. Map Yearly Financials (with Chart Key Mapping)
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
        "profit_before_tax": "profit_before_tax",
        "tax_pct": "tax_pct",
        "other_income": "other_income",
        "interest": "interest",
        "depreciation": "depreciation",
        "expenses": "expenses",
        "net_profit_margin": "net_profit_margin",
        "equity_capital": "equity_capital",
        "total_liabilities": "total_liabilities",
        "fixed_assets": "fixed_assets",
        "cwip": "cwip",
        "investments": "investments",
        "other_assets": "other_assets",
        "total_assets": "total_assets",
        "cash_flow_operating": "cash_flow_operating",
        "cash_flow_investing": "cash_flow_investing",
        "cash_flow_financing": "cash_flow_financing",
        "net_cash_flow": "net_cash_flow",
        "book_value": "book_value",
        "pe_ratio": "pe_ratio",
        "dividend_yield": "dividend_yield"
    }

    yearly_financials = {}
    fin = fr.get("financials", {})
    statements = [
        fin.get("income_statement", {}),
        fin.get("balance_sheet", {}),
        fin.get("cash_flow", {}),
        fin.get("ratios_table", {})
    ]
    
    seen_points = {}
    for stmt in statements:
        if not stmt: continue
        for period, data in stmt.items():
            if not isinstance(data, dict): continue
            for metric_key, val_obj in data.items():
                val = val_obj.get("value") if isinstance(val_obj, dict) else val_obj
                if val is None: continue
                
                target_key = CHART_MAP.get(metric_key, metric_key)
                if target_key not in seen_points:
                    seen_points[target_key] = {}
                
                if period not in seen_points[target_key]:
                    seen_points[target_key][period] = val

    def _sort_key(p_dict):
        p = p_dict["period"]
        if p == "TTM": return "9999-12-31"
        try:
            parts = p.split()
            if len(parts) == 2:
                month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                            "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                return f"{parts[1]}-{month_map.get(parts[0], '00')}-01"
        except: pass
        return p

    for m_key, points in seen_points.items():
        list_points = [{"period": p, "value": v} for p, v in points.items()]
        list_points.sort(key=_sort_key)
        yearly_financials[m_key] = list_points

    return {
        "symbol": symbol,
        "company": {
            "name": company.get("name") or fr.get("company", {}).get("name") or symbol,
            "sector": company.get("sector") or fr.get("company", {}).get("sector") or "Unknown",
            "about": company.get("about") or fr.get("company", {}).get("about", "")
        },
        "fundametrics_metrics": fundametrics_metrics,
        "yearly_financials": yearly_financials,
        "shareholding": fr.get("shareholding"),
        "metadata": fr.get("metadata", {}),
        "ai_summary": fr.get("ai_summary", {"paragraphs": []}),
        "signals": fr.get("signals", []),
        "news": fr.get("news", []),
        "live_market": live_market,
        "management": fr.get("management", []),
        "reliability": {
            "coverage_score": trust_report.get("coverage_score", 0) if trust_report else 0,
            "status": "good" if trust_report and trust_report.get("coverage_score", 0) > 0.8 else "partial" if trust_report and trust_report.get("coverage_score", 0) > 0.5 else "poor",
            "missing": trust_report.get("missing_blocks", []) if trust_report else [],
            "last_audit": trust_report.get("generated_at") if trust_report else None
        }
    }


def _build_ui_response(
    company: Dict,
    income_statements: List[Dict],
    balance_sheets: List[Dict],
    cash_flows: List[Dict],
    metrics: List[Dict],
    ownership: Optional[Dict],
    trust_report: Optional[Dict] = None,
    live_market: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build Phase 20 UI-compatible response from MongoDB data
    """
    symbol = company.get("symbol", company.get("_id"))
    
    yearly_financials = {}
    metrics_map = {}
    
    CHART_MAP = {
        "Sales": "revenue",
        "Revenue": "revenue",
        "revenue": "revenue",
        "Expenses": "expenses",
        "expenses": "expenses",
        "Operating Profit": "operating_profit",
        "operating_profit": "operating_profit",
        "Profit before tax": "profit_before_tax",
        "profit_before_tax": "profit_before_tax",
        "Net Profit": "net_income",
        "net_profit": "net_income",
        "net_income": "net_income",
        "EPS": "eps",
        "eps": "eps",
        "Reserves": "reserves",
        "reserves": "reserves",
        "Borrowings": "borrowings",
        "borrowings": "borrowings",
        "Total Assets": "total_assets",
        "total_assets": "total_assets",
        "Cash from Operating Activity": "cash_flow_operating",
        "cash_flow_operating": "cash_flow_operating",
        "Cash from Investing Activity": "cash_flow_investing",
        "cash_flow_investing": "cash_flow_investing",
        "Cash from Financing Activity": "cash_flow_financing",
        "cash_flow_financing": "cash_flow_financing",
        "ROE": "roe",
        "roe": "roe",
        "ROE %": "roe",
        "ROCE": "roce",
        "roce": "roce",
        "ROCE %": "roce",
        "Net Profit Margin": "net_profit_margin",
        "net_profit_margin": "net_profit_margin",
        "OPM %": "operating_profit_margin",
        "Operating Profit Margin": "operating_profit_margin",
        "operating_profit_margin": "operating_profit_margin",
        "Pe Ratio": "pe_ratio",
        "P/E Ratio": "pe_ratio",
        "pe_ratio": "pe_ratio",
        "Dividend Yield": "dividend_yield",
        "dividend_yield": "dividend_yield",
        "Face Value": "face_value",
        "face_value": "face_value",
        "Book Value": "book_value",
        "book_value": "book_value"
    }

    # Fallback to fundametrics_response blob if collections are empty
    if not income_statements:
        fr = company.get("fundametrics_response", {})
        financials = fr.get("financials", {})
        if financials:
            is_stmt = financials.get("income_statement", {})
            bs_stmt = financials.get("balance_sheet", {})
            cf_stmt = financials.get("cash_flow", {})
            rt_stmt = financials.get("ratios_table", {})
            
            for stmt in [is_stmt, bs_stmt, cf_stmt, rt_stmt]:
                if not stmt: continue
                for period, items in stmt.items():
                    if not isinstance(items, dict): continue
                    for k, v in items.items():
                        val = v.get("value") if isinstance(v, dict) else v
                        if val is None: continue
                        
                        target_key = CHART_MAP.get(k, k.lower().replace(' ', '_'))
                        if target_key not in metrics_map:
                            metrics_map[target_key] = []
                        metrics_map[target_key].append({"period": period, "value": val})

    def add_to_map(data_dict, period):
        for k, v in data_dict.items():
            period_str = str(period)
            if len(period_str) == 4 and period_str.isdigit():
                period_str = f"Mar {period_str}"

            target_key = CHART_MAP.get(k, k.lower().replace(' ', '_'))
            if target_key not in metrics_map:
                metrics_map[target_key] = []
            metrics_map[target_key].append({"period": period_str, "value": v})

    for stmt in income_statements:
        add_to_map(stmt["data"], stmt["year"])
    for stmt in balance_sheets:
        add_to_map(stmt["data"], stmt["year"])
    for stmt in cash_flows:
        add_to_map(stmt["data"], stmt["year"])
    
    # Sort chronological for charts
    def _sort_key(p_dict):
        p = p_dict["period"]
        if p == "TTM": return "9999-12-31"
        try:
            parts = p.split()
            if len(parts) == 2:
                month_map = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                            "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                return f"{parts[1]}-{month_map.get(parts[0], '00')}-01"
            if len(p) == 4 and p.isdigit():
                return f"{p}-03-31"
        except: pass
        return p

    for m_key in metrics_map:
        metrics_map[m_key].sort(key=_sort_key)
        
    yearly_financials = metrics_map
    
    # Build fundametrics_metrics (for Executive Snapshot & Insights)
    fundametrics_metrics = []
    seen_metrics = set()
    
    def _normalize_name(name: str) -> str:
        # Clean: remove prefix, replace _ with space, title case
        n = name.replace("fundametrics_", "").replace("_", " ").title()
        
        # Aggressive normalization for core snapshot metrics
        NAME_MAP = {
            "Net Profit Margin": "Net Margin",
            "Earnings Per Share": "Eps",
            "Price To Earnings": "PE Ratio",
            "Pe Ratio": "PE Ratio",
            "Roe": "ROE",
            "Roce": "ROCE",
            "Return On Equity": "ROE",
            "Return On Capital Employed": "ROCE",
            "Eps": "EPS",
            "Operating Profit Margin": "Operating Margin"
        }
        return NAME_MAP.get(n, n)

    for metric in metrics:
        name = _normalize_name(metric["metric_name"])
        if name not in seen_metrics:
            # We only show metrics with values
            val = metric.get("value")
            if val is not None:
                fundametrics_metrics.append({
                    "metric_name": name,
                    "value": val,
                    "unit": metric.get("unit", ""),
                    "confidence": metric.get("confidence", 0),
                    "trust_score": metric.get("trust_score", {"grade": "N/A", "score": 0}),
                    "drift": metric.get("drift", {"flag": "neutral", "z_score": 0}),
                    "explainability": metric.get("explainability", {}),
                    "source_provenance": metric.get("source_provenance", {})
                })
                seen_metrics.add(name)
    
    # Ensure "Current Price" is handled
    price_val = None
    if live_market and live_market.get("price") and live_market["price"].get("value"):
        price_val = live_market["price"]["value"]
    
    if "Current Price" not in seen_metrics:
        # If not from live_market, try metadata/blob
        if price_val is None:
            # Try metadata first
            price_val = company.get("price", {}).get("value")
            if price_val is None:
                # Try fundametrics_response blob
                fr = company.get("fundametrics_response", {})
                m_values = fr.get("metrics", {}).get("values", {})
                p_obj = m_values.get("Current Price") or m_values.get("fundametrics_current_price")
                price_val = p_obj.get("value") if isinstance(p_obj, dict) else p_obj
        
        if price_val is not None:
            fundametrics_metrics.append({
                "metric_name": "Current Price",
                "value": price_val,
                "unit": "INR",
                "confidence": 0.95,
                "trust_score": {"grade": "A", "score": 95},
                "drift": {"flag": "neutral"},
                "explainability": {"formula": "Latest market price"}
            })
            seen_metrics.add("Current Price")
    elif price_val is not None:
        # Update existing Current Price with live value if available
        for m in fundametrics_metrics:
            if m["metric_name"] == "Current Price":
                m["value"] = price_val
                break

    # Priority Sort for Snapshot (Executive Snapshot renders top 12)
    PRIORITY = [
        "Current Price",
        "Market Cap",
        "PE Ratio",
        "ROE",
        "ROCE",
        "Dividend Yield",
        "Debt To Equity",
        "EPS",
        "Operating Margin",
        "Net Margin",
        "Sales Growth 5Y",
        "Profit Growth 5Y"
    ]
    
    sorted_metrics = []
    # 1. Add prioritized ones in exact order
    for p_name in PRIORITY:
        for m in fundametrics_metrics:
            if m["metric_name"] == p_name:
                sorted_metrics.append(m)
                break
    
    # 2. Add everything else alphabetically
    snapshot_names = {sm["metric_name"] for sm in sorted_metrics}
    remaining = [m for m in fundametrics_metrics if m["metric_name"] not in snapshot_names]
    remaining.sort(key=lambda x: x["metric_name"])
    sorted_metrics.extend(remaining)
    
    fundametrics_metrics = sorted_metrics
    
    fr_comp = company.get("fundametrics_response", {}).get("company", {})
    company_block = {
        "name": company.get("name") or fr_comp.get("name") or symbol,
        "sector": company.get("sector") if (company.get("sector") and company.get("sector") != "Unknown") else fr_comp.get("sector") or "General",
        "industry": company.get("industry") if (company.get("industry") and company.get("industry") != "Unknown") else fr_comp.get("industry") or "General",
        "about": company.get("about") or fr_comp.get("about", "")
    }
    
    shareholding_block = { "status": "unavailable", "summary": {}, "insights": [] }
    if ownership:
        summary = ownership.get("summary", {})
        if not summary:
            summary = {
                "promoters": ownership.get("promoters", 0),
                "fii": ownership.get("fii", 0),
                "dii": ownership.get("dii", 0),
                "public": ownership.get("public", 0),
                "others": ownership.get("others", 0)
            }
        
        shareholding_block = {
            "status": "available",
            "summary": summary,
            "insights": ownership.get("insights", []),
            "history": ownership.get("history", [{
                "period": ownership.get("quarter", "Dec 2024"),
                "promoter": summary.get("promoters"),
                "fii": summary.get("fii"),
                "dii": summary.get("dii"),
                "public": summary.get("public")
            }])
        }
    
    last_updated = company.get("last_updated")
    if isinstance(last_updated, str):
        scraped_at = last_updated
    elif hasattr(last_updated, "isoformat"):
        scraped_at = last_updated.isoformat()
    else:
        scraped_at = datetime.now(timezone.utc).isoformat()

    metadata_block = {
        "scraped_at": scraped_at,
        "financial_period_label": "Latest Available",
        "quarterly_period_label": "Latest Quarter",
        "yearly_period_label": "Latest FY",
        "ratios_period_label": "Latest FY",
        "trends_period_label": "Multi-year",
        "run_id": f"mongo-{symbol}-001",
        "as_of_date": "Latest",
        "computation_engine": "Fundametrics Quant Engine v2.4 (MongoDB)",
        "data_sources": company.get("data_sources", {}),
        "data_quality_notes": ["Data sourced from MongoDB Atlas"],
        "ai_summary_generated": False
    }
    
    coverage_score = 0.0
    missing_blocks = []
    reliability_status = "poor"
    
    if trust_report:
        coverage_score = trust_report.get("coverage_score", 0)
        missing_blocks = trust_report.get("missing_blocks", [])
        
        if coverage_score > 0.8:
            reliability_status = "good"
        elif coverage_score > 0.5:
            reliability_status = "partial"
        else:
            reliability_status = "poor"
    
    is_stale = False
    generated_at = trust_report.get("generated_at") if trust_report else None
    if generated_at:
        try:
            if isinstance(generated_at, str):
                gen_dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            else:
                gen_dt = generated_at
            
            days_old = (datetime.now(timezone.utc) - gen_dt).days
            if days_old > 365:
                is_stale = True
        except:
            pass

    response = {
        "symbol": symbol,
        "company": company_block,
        "fundametrics_metrics": fundametrics_metrics,
        "yearly_financials": yearly_financials,
        "shareholding": shareholding_block,
        "metadata": metadata_block,
        "reliability": {
            "coverage_score": coverage_score,
            "status": reliability_status,
            "missing": missing_blocks,
            "is_stale": is_stale,
            "last_audit": generated_at
        },
        "ai_summary": {
            "paragraphs": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "generated": False,
            "mode": "historical-only",
            "advisory": False,
            "explainability_available": True
        },
        "signals": [],
        "news": None,
        "management": None
    }
    
    return response



@router.get("/health")
async def health_check():
    """Check MongoDB connection health"""
    try:
        client = get_client()
        await client.admin.command('ping')
        
        stats = await mongo_repo.get_stats()
        
        return {
            "status": "healthy",
            "database": "MongoDB Atlas",
            "collections": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/sectors")
async def get_all_sectors():
    """List all unique sectors available in the MongoDB repository."""
    col = get_companies_col()
    sectors = await col.distinct("sector")
    return sorted([s for s in sectors if s])


@router.get("/indices")
def get_available_indices():
    """List all available indices."""
    return list(INDEX_CONSTITUENTS.keys())


# Global Cache Initialization (Phase 13: High-Performance Architecture)
_HARD_FALLBACK_PRICES = [
    {"id": "NIFTY 50", "label": "NIFTY 50", "price": 24345.50, "change": 12.45, "changePercent": 0.05, "symbol": "^NSEI"},
    {"id": "SENSEX", "label": "SENSEX", "price": 80123.15, "change": -45.60, "changePercent": -0.06, "symbol": "^BSESN"},
    {"id": "BANK NIFTY", "label": "BANK NIFTY", "price": 52678.90, "change": 156.30, "changePercent": 0.30, "symbol": "^NSEBANK"},
    {"id": "NIFTY IT", "label": "NIFTY IT", "price": 38456.25, "change": -210.15, "changePercent": -0.54, "symbol": "^CNXIT"}
]

# Use a specific list constructor to prevent mutation issues
INDEX_PRICES_CACHE = list(_HARD_FALLBACK_PRICES)
INDEX_PRICES_TS = datetime.now()
INDEX_CACHE = {} # key: index_name_limit, value: (timestamp, data)

_indices_lock = asyncio.Lock()
_constituents_lock = asyncio.Lock()

async def _save_market_data(key: str, data: Any):
    """Internal helper to persist cache to MongoDB for UI Immortality"""
    try:
        db = get_db()
        col = db["market_data"]
        await col.update_one(
            {"_id": key},
            {"$set": {
                "data": data,
                "updated_at": datetime.now(timezone.utc),
                "type": "cache_bridge"
            }},
            upsert=True
        )
    except Exception as e:
        logging.error(f"Failed to persist market data {key}: {e}")

async def seed_market_data():
    """Seed memory caches from MongoDB on boot (Phase 11)"""
    global INDEX_PRICES_CACHE, INDEX_PRICES_TS, INDEX_CACHE
    try:
        db = get_db()
        col = db["market_data"]
        
        # 1. Seed Index Prices (with Sanity Check)
        doc = await col.find_one({"_id": "index_prices"})
        if doc and doc.get("data") and len(doc["data"]) > 0:
            # Audit data: ensure at least one price is real
            has_real_prices = any(item.get("price") for item in doc["data"])
            if has_real_prices:
                async with _indices_lock:
                    INDEX_PRICES_CACHE = doc["data"]
                    INDEX_PRICES_TS = doc.get("updated_at", datetime.now())
                logging.info(f"⭐ Memory seeded: {len(doc['data'])} Index Prices (from MongoDB)")
            else:
                logging.warning("⚠️ Seed Warning: MongoDB record for 'index_prices' exists but contains no numeric prices. Staying on Hard Fallback.")
            
        # 2. Seed Index Constituents
        cursor = col.find({"type": "cache_bridge", "_id": {"$regex": "^index_cache_"}})
        async for doc in cursor:
            cache_key = doc["_id"].replace("index_cache_", "")
            if doc.get("data"):
                async with _constituents_lock:
                    INDEX_CACHE[cache_key] = (doc.get("updated_at", datetime.now()), doc["data"])
        # 3. Nuclear Hydration (Phase 16: Top 100 Dominance)
        # Recursively repairs snapshots AND tags Market Leaders for priority sorting.
        async def nuclear_hydration():
            from pymongo import UpdateOne
            from scraper.core.indices import INDEX_CONSTITUENTS
            col = get_companies_col()
            
            # Identify Top 100 (Nifty 50 + Sensex) for priority tagging
            famous_symbols = set(INDEX_CONSTITUENTS.get("NIFTY 50", []) + INDEX_CONSTITUENTS.get("SENSEX", []))
            
            # Find everything that needs a display repair OR priority tagging
            cursor = col.find({
                "$or": [
                    {"snapshot": {"$exists": False}}, 
                    {"snapshot.marketCap": {"$in": [None, 0]}},
                    {"snapshot.priority": {"$exists": False}, "symbol": {"$in": list(famous_symbols)}}
                ],
                "fundametrics_response": {"$exists": True}
            })
            
            total_repaired = 0
            batch = []
            async for doc in cursor:
                fr = doc.get("fundametrics_response", {})
                m_list = fr.get("fundametrics_metrics", [])
                deep_metrics = fr.get("metrics", {}).get("values", [])
                symbol = doc.get("symbol")
                
                m_map = {m.get("metric_name"): m.get("value") for m in m_list if isinstance(m, dict) and m.get("metric_name")}
                mcap = m_map.get("Market Cap") or m_map.get("Market_Cap") or doc.get("market_cap")
                price = m_map.get("Current Price") or m_map.get("Price") or doc.get("price")
                
                # Deeper lookup for Phase 15/16 (Old Blobs + Activity support)
                change_pct = 0.0
                if (not mcap or not price) and isinstance(deep_metrics, list):
                    for m in deep_metrics:
                        if not mcap and m.get("metric") in ["Market Cap", "Market_Cap", "MCAP"]: mcap = m.get("value")
                        if not price and m.get("metric") in ["Price", "Current Price"]: price = m.get("value")
                        if m.get("metric") in ["Change Percent", "Change_Percent"]: change_pct = m.get("value") or 0.0

                if mcap or price or symbol in famous_symbols:
                    priority = 10 if symbol in famous_symbols else 0
                    batch.append(UpdateOne({"_id": doc["_id"]}, {"$set": {
                        "snapshot": {
                            "symbol": symbol, "name": doc.get("name"),
                            "marketCap": mcap, "currentPrice": price, 
                            "changePercent": change_pct, "priority": priority,
                            "pe": doc.get("pe"), "roe": doc.get("roe"),
                            "sector": doc.get("sector") or fr.get("company", {}).get("sector")
                        }
                    }}))
                    
                    if len(batch) >= 100:
                        try:
                            await col.bulk_write(batch, ordered=False)
                            total_repaired += len(batch)
                            batch = []
                        except: batch = []
            
            if batch:
                try:
                    await col.bulk_write(batch, ordered=False)
                    total_repaired += len(batch)
                except: pass
                
            if total_repaired > 0:
                logging.info(f"⚡ NUCLEAR HYDRATION: Repaired {total_repaired} records with Top-100 Priority.")

        asyncio.create_task(nuclear_hydration())
        
        # 4. Final Sanity Audit (Ensure dashboard is NEVER empty)
        if not INDEX_PRICES_CACHE:
            async with _indices_lock:
                INDEX_PRICES_CACHE = list(_HARD_FALLBACK_PRICES)
            logging.error("⚠️ CRITICAL RECOVERY: INDEX_PRICES_CACHE was empty on boot. Applied Hard Fallback.")
            
    except Exception as e:
        logging.error(f"Failed to seed market data: {e}")

async def refresh_index_prices():
    """Background task to update index prices without blocking API."""
    global INDEX_PRICES_CACHE, INDEX_PRICES_TS
    
    session = await YahooSession.get_instance()
    if session.is_in_quarantine():
        return # Respect lockout

    names = list(YAHOO_INDEX_MAP.keys())
    symbols = list(YAHOO_INDEX_MAP.values())
    
    try:
        results = await asyncio.wait_for(
            market_engine.fetch_batch_prices(symbols),
            timeout=15.0
        )
        
        response = []
        for name, data in zip(names, results):
            if data and (data.get("price") or data.get("currentPrice")):
                p = data.get("price") or data.get("currentPrice")
                response.append({
                    "id": name, "label": name, "price": p,
                    "change": data.get("change") or 0,
                    "changePercent": data.get("change_percent") or data.get("changePercent") or 0,
                    "symbol": data.get("symbol") or symbols[names.index(name)]
                })
        
        if response:
            async with _indices_lock:
                # PHASE 15 BUG FIX: Preserve non-zero gains during market-off hours
                # If new data has 0.0% gain but old data had something else, keep the old gain.
                old_map = {item["id"]: item for item in INDEX_PRICES_CACHE}
                final_response = []
                for new_item in response:
                    old_item = old_map.get(new_item["id"])
                    if old_item and new_item["changePercent"] == 0.0 and old_item["changePercent"] != 0.0:
                        new_item["change"] = old_item["change"]
                        new_item["changePercent"] = old_item["changePercent"]
                    final_response.append(new_item)

                INDEX_PRICES_CACHE = final_response
                INDEX_PRICES_TS = datetime.now()
            
            # Phase 11: Nuclear Persistence
            await _save_market_data("index_prices", final_response)
            logging.info(f"✅ Index prices refreshed (Gain Preserved): {len(final_response)} items")
            
    except Exception as e:
        logging.error(f"Failed background price refresh: {e}")

async def refresh_all_indices_constituents():
    """Update constituents for core indices in background."""
    indices = ["NIFTY 50", "SENSEX", "BANK NIFTY"]
    for idx in indices:
        await refresh_index_constituents_manual(idx, limit=12)
        await asyncio.sleep(2) # Prevent burst

async def refresh_index_constituents_manual(index_name: str, limit: int = 12):
    """Core logic to fetch constituents and update cache."""
    global INDEX_CACHE
    index_name = index_name.upper()
    cache_key = f"{index_name}_{limit}"
    
    try:
        symbols = get_constituents(index_name)
        if not symbols: return
        
        request_symbols = symbols[:limit] if limit else symbols
        results = await mongo_repo.get_companies_detail(request_symbols)
        
        # Enrichment
        top_symbols = request_symbols
        yahoo_symbols = [f"{s}.NS" if not s.endswith(".NS") else s for s in top_symbols]
        
        price_map = {}
        # Only try network if NOT in quarantine
        session = await YahooSession.get_instance()
        if not session.is_in_quarantine():
            try:
                live_prices = await asyncio.wait_for(
                    market_engine.fetch_batch_prices(yahoo_symbols),
                    timeout=15.0
                )
                for sym, p_data in zip(top_symbols, live_prices):
                    if p_data and p_data.get("price"):
                        price_map[sym] = p_data.get("price")
            except: pass

        # DB Fallback if network failed or quarantined
        for c in results:
            if c["symbol"] in top_symbols and c.get("currentPrice") and c["symbol"] not in price_map:
                price_map[c["symbol"]] = c["currentPrice"]

        symbol_map = {c["symbol"]: c for c in results}
        ordered_results = []
        for s in request_symbols:
            if s in symbol_map:
                c_data = symbol_map[s]
                if s in price_map:
                    c_data["currentPrice"] = price_map[s]
                ordered_results.append(c_data)
            
        response_data = {
            "index": index_name,
            "count": len(ordered_results),
            "constituents": ordered_results
        }
        
        async with _constituents_lock:
            INDEX_CACHE[cache_key] = (datetime.now(), response_data)
        
        # Phase 11: Nuclear Persistence
        await _save_market_data(f"index_cache_{cache_key}", response_data)
        logging.info(f"✅ Cache refreshed and persisted for index: {index_name}")
            
    except Exception as e:
        logging.error(f"Refresh failed for {index_name}: {e}")


@router.get("/indices/prices")
async def get_indices_overview():
    """ZERO-BLOCKING: Returns index prices instantly from memory-cache."""
    # Ensure we NEVER return an empty list (Phase 14 Continuity)
    if not INDEX_PRICES_CACHE:
         return _HARD_FALLBACK_PRICES
    return INDEX_PRICES_CACHE


@router.get("/indices/{index_name}/constituents")
async def get_index_constituents_mongo(
    index_name: str,
    limit: Optional[int] = Query(None, ge=1, le=100)
):
    """ZERO-BLOCKING: Returns constituents instantly from memory-cache."""
    index_name = index_name.upper()
    cache_key = f"{index_name}_{limit}"
    
    # Return from cache if exact match exists
    if cache_key in INDEX_CACHE:
        return INDEX_CACHE[cache_key][1]
    
    # Check if we have anything at all for this index (UX win: show partial match)
    partial_match = next((v[1] for k, v in INDEX_CACHE.items() if k.startswith(index_name)), None)
    if partial_match:
        # Trigger specific limit refresh in background
        asyncio.create_task(refresh_index_constituents_manual(index_name, limit))
        return partial_match

    # PHASE 14 RADICAL CONTINUITY: 
    # If absolute cache miss (fresh startup), perform an IMMEDIATE low-latency DB lookup.
    # This adds ~40-60ms but guarantees the user sees companies instantly.
    try:
        symbols = get_constituents(index_name)
        if symbols:
            request_symbols = symbols[:limit] if limit else symbols
            results = await mongo_repo.get_companies_detail(request_symbols)
            
            if results:
                response_data = {
                    "index": index_name,
                    "count": len(results),
                    "constituents": results,
                    "metadata": {"source": "db_immediate_fallback"}
                }
                # Seed cache so next hit is <1ms
                async with _constituents_lock:
                    INDEX_CACHE[cache_key] = (datetime.now(), response_data)
                
                # Trigger price refresh in background
                asyncio.create_task(refresh_index_constituents_manual(index_name, limit))
                return response_data
    except Exception as e:
        logging.error(f"Immediate DB fallback failed for {index_name}: {e}")

    return {"index": index_name, "count": 0, "constituents": []}


@router.get("/coverage")
async def list_coverage_mongo():
    """Summarize data coverage across all processed companies in MongoDB."""
    companies = await mongo_repo.get_all_companies()
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "symbols": len(companies),
        },
        "results": [
            {
                "symbol": c["symbol"],
                "name": c["name"],
                "sector": c["sector"],
                "coverage": {"score": 0.95, "full": True} # Placeholder
            }
            for c in companies
        ]
    }

@router.get("/sitemap.xml")
@limiter.limit("10/minute")
async def get_sitemap(request: Request):
    """
    Generate dynamic sitemap.xml for SEO
    """
    base_url = "https://fundametrics.in"
    
    # 1. Get all symbols
    symbols = await mongo_repo.get_all_symbols()
    
    # 2. Build XML
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # Static pages (Standardized with trailing slashes to match redirects)
    static_pages = [
        "",
        "/stocks/",
        "/about/"
    ]
    
    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    for page in static_pages:
        prio = '1.0' if page == '' else '0.8'
        xml.append(f"""  <url>
    <loc>{base_url}{page}</loc>
    <lastmod>{current_date}</lastmod>
    <changefreq>daily</changefreq>
    <priority>{prio}</priority>
  </url>""")

    # Company pages
    for symbol in symbols:
        if not symbol or symbol.startswith("--"): continue
        xml.append(f"""  <url>
    <loc>{base_url}/stocks/{symbol}</loc>
    <lastmod>{current_date}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")
    
    xml.append('</urlset>')
    
    return Response(content="\n".join(xml), media_type="application/xml")
@router.get("/stocks/{symbol}/market")
async def get_market_facts_mongo(symbol: str):
    """
    Enhanced market facts with MongoDB persistence fallback (Phase 11/12).
    Ensures 'Updating Price' doesn't persist during Yahoo lockdowns.
    """
    symbol = symbol.upper()
    try:
        # Layer 1: Attempt live fetch (Engine handles quarantine check internally)
        market_facts = await market_engine.fetch_market_facts(symbol)

        # PERSISTENCE: Save successful live fetch to MongoDB Snapshot (Phase 23)
        # This ensures Top Gainers/Losers and other DB queries interact with fresh data
        if market_facts.current_price:
            try:
                payload = {
                    "snapshot.currentPrice": market_facts.current_price,
                    "snapshot.change": market_facts.current_change,
                    "snapshot.changePercent": market_facts.change_percent,
                    "snapshot.marketCap": market_facts.market_cap,
                    "snapshot.fiftyTwoWeekHigh": market_facts.fifty_two_week_high,
                    "snapshot.fiftyTwoWeekLow": market_facts.fifty_two_week_low,
                    "snapshot.lastUpdated": datetime.now(timezone.utc)
                }
                # Clean payload (remove None values to avoid overwriting existing data with null)
                payload = {k: v for k, v in payload.items() if v is not None}
                
                # Fire-and-forget update to avoid blocking the response
                asyncio.create_task(mongo_repo.upsert_company(symbol, payload))
            except Exception as e:
                logging.error(f"Failed to persist market data for {symbol}: {e}")
        
        # Layer 2: If live failed or blocked, try MongoDB Registry/Snapshot
        if not market_facts.current_price:
            logging.debug(f"Live fetch failed for {symbol}, attempting DB fallback...")
            db_data = await mongo_repo.get_company(symbol)
            if db_data:
                # Try snapshot first
                snap = db_data.get("snapshot", {})
                price = snap.get("currentPrice")
                mcap = snap.get("marketCap")
                
                # If snapshot is empty, try fundametrics_response blob
                if not price:
                    fr = db_data.get("fundametrics_response", {})
                    m_list = fr.get("fundametrics_metrics", [])
                    for m in m_list:
                        if isinstance(m, dict) and m.get("metric_name") == "Current Price":
                            price = m.get("value")
                            break
                
                if price:
                    from scraper.core.market_facts_engine import MarketFacts
                    market_facts = MarketFacts(
                        current_price=price,
                        current_change=0.0, # Neutral fallback
                        change_percent=0.0,
                        price_currency=snap.get("currency", "INR"),
                        price_delay_minutes=0, # Historical/Cached
                        fifty_two_week_high=snap.get("fiftyTwoWeekHigh"),
                        fifty_two_week_low=snap.get("fiftyTwoWeekLow"),
                        market_cap=mcap,
                        shares_outstanding=snap.get("sharesOutstanding")
                    )

        market_block = market_engine.build_market_block(market_facts)
        
        return {
            "symbol": symbol,
            "market": market_block,
            "api_contract": {
                "data_type": "facts_plus_fallback",
                "source": "live" if market_facts.current_price and not market_facts.price_delay_minutes == 0 else "db_cache",
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        }
    except Exception as e:
        import traceback
        logging.error(f"Failed to fetch market facts for {symbol}: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
