"""
MongoDB-based API Routes - Phase 22

This module provides API endpoints that use MongoDB instead of SQLite.
Start with /stocks/{symbol} for RELIANCE as proof of concept.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, timezone
import os

# MongoDB connection string (hardcoded for Phase 22 testing)
# In production, this should come from environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://admin:Mohit%4015@cluster0.tbhvlm3.mongodb.net/fundametrics?retryWrites=true&w=majority")

from scraper.core.mongo_repository import MongoRepository
from scraper.core.db import get_client, get_db, get_companies_col
from scraper.core.indices import INDEX_CONSTITUENTS, get_constituents

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()
mongo_repo = MongoRepository(get_db())


@router.get("/companies")
async def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get list of companies with basic info (Phase 23)
    Supports pagination.
    """
    try:
        col = get_companies_col()
        total = await col.count_documents({"symbol": {"$not": {"$regex": "^--"}}})
        
        companies = await mongo_repo.get_all_companies(skip=skip, limit=limit)
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "count": len(companies),
            "companies": companies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch companies: {str(e)}")


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
        
        # 2. Get financials (all statement types)
        income_statements = await mongo_repo.get_financials_annual(symbol, "income_statement")
        balance_sheets = await mongo_repo.get_financials_annual(symbol, "balance_sheet")
        cash_flows = await mongo_repo.get_financials_annual(symbol, "cash_flow")
        
        # 3. Get metrics
        metrics = await mongo_repo.get_metrics(symbol)
        
        # 4. Get ownership
        ownership = await mongo_repo.get_ownership(symbol)

        # Fallback: Extract from stored blob if normalized collections are empty
        fundametrics_response = company.get("fundametrics_response", {})
        if not income_statements and "financials" in fundametrics_response:
             # Basic extraction - in real app we might want proper normalization
             # For now, just pass empty lists and let _build_ui_response handle using the raw response if possible
             # OR better: Return the pre-built fundametrics_response directly if it exists!
             pass
        
        if fundametrics_response and (not income_statements and not metrics):
             # Fast path: Transform the stored Fundametrics Response blob to UI structure
             trust_report = await mongo_repo.get_trust_report(symbol)
             return _transform_fundametrics_response(symbol, company, fundametrics_response, trust_report)

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
            trust_report=trust_report
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
    
    Args:
        q or query: Search string
        
    Returns:
        {
            "query": str,
            "results": List[{symbol, name, sector}],
            "disclaimer": str
        }
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
        
        # Search in registry (includes non-ingested companies)
        search_regex = {"$regex": search_term.strip(), "$options": "i"}
        registry_results = await registry_col.find(
            {
                "$or": [
                    {"symbol": search_regex},
                    {"name": search_regex}
                ]
            },
            {"_id": 0, "symbol": 1, "name": 1, "sector": 1}
        ).limit(25).to_list(length=25)
        
        # Get analyzed symbols to determine status
        analyzed_cursor = companies_col.find({}, {"symbol": 1, "_id": 0})
        analyzed_symbols = {doc["symbol"] async for doc in analyzed_cursor}
        
        results = [
            {
                "symbol": c["symbol"],
                "name": c["name"],
                "sector": c.get("sector", "General"),
                "status": "available" if c["symbol"] in analyzed_symbols else "not_available"
            }
            for c in registry_results
        ]
        
        return {
            "query": search_term,
            "results": results,
            "disclaimer": "Search results are informational only and do not constitute investment advice."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


def _transform_fundametrics_response(symbol: str, company: Dict, fr: Dict, trust_report: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Transform the internal Fundametrics Response blob (from ResponseBuilder) 
    into the UI-compatible structure expected by the Phase 20/23 Frontend.
    """
    # 1. Map Metrics to List (Deduplicated & Normalized)
    metrics_block = fr.get("metrics", {})
    raw_metrics = metrics_block.get("values", {})
    ratios = metrics_block.get("ratios", {})
    
    combined_metrics: Dict[str, Dict[str, Any]] = {}
    
    for source in [ratios, raw_metrics]:
        if not isinstance(source, dict): continue
        for key, data in source.items():
            if not isinstance(data, dict): continue
            
            display_name = key.replace("fundametrics_", "").replace("_", " ").title()
            
            # Normalization map for consistency with MetricCardDense and Snapshot
            NAME_MAP = {
                "Net Profit Margin": "Net Margin",
                "Earnings Per Share": "Eps",
                "Price To Earnings": "Pe Ratio",
                "Operating Profit Margin": "Operating Margin",
                "Operating Margin": "Operating Margin",
                "Return On Equity": "ROE",
                "Return On Capital Employed": "ROCE",
                "Market Cap": "Market Cap",
                "Debt To Equity": "Debt To Equity",
                "fundametrics_operating_margin": "Operating Margin",
                "fundametrics_debt_to_equity": "Debt To Equity"
            }
            display_name = NAME_MAP.get(display_name, display_name)
            
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
            if isinstance(m, dict) and m.get("metric_name") and m["metric_name"] not in combined_metrics:
                combined_metrics[m["metric_name"]] = m

    fundametrics_metrics = list(combined_metrics.values())

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
        "Profit before tax": "profit_before_tax",
        "profit_before_tax": "profit_before_tax",
        "Tax %": "tax_pct",
        "tax_pct": "tax_pct",
        "Other Income": "other_income",
        "other_income": "other_income",
        "Interest": "interest",
        "interest": "interest",
        "Depreciation": "depreciation",
        "depreciation": "depreciation",
        "Expenses": "expenses",
        "expenses": "expenses",
        "Net Profit Margin": "net_profit_margin",
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
                
                # Keep first value for period (prioritize earlier statements)
                if period not in seen_points[target_key]:
                    seen_points[target_key][period] = val

    # Helper for sorting periods
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
    trust_report: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Build Phase 20 UI-compatible response from MongoDB data
    
    This matches the structure expected by the frontend components.
    """
    symbol = company.get("symbol", company.get("_id"))
    
    # Build yearly_financials (for tables & charts)
    yearly_financials = {}
    
    # Organize by year
    # group by metric
    metrics_map = {}
    
    # Key mapping for frontend consistency
    CHART_MAP = {
        "Sales": "revenue",
        "Revenue": "revenue",
        "revenue": "revenue",
        "Expenses": "expenses",
        "expenses": "expenses",
        "Operating Profit": "operating_profit",
        "operating_profit": "operating_profit",
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
        "ROCE": "roce",
        "roce": "roce",
        "Net Profit Margin": "net_profit_margin",
        "net_profit_margin": "net_profit_margin",
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

    def add_to_map(data_dict, period):
        for k, v in data_dict.items():
            # Handle period formatting (e.g. 2024 -> "Mar 2024" or just stringify)
            period_str = str(period)
            if len(period_str) == 4 and period_str.isdigit():
                period_str = f"Mar {period_str}" # Heuristic for annual

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
    
    yearly_financials = metrics_map
    
    # Build fundametrics_metrics (for Executive Snapshot & Insights)
    fundametrics_metrics = []
    for metric in metrics:
        fundametrics_metrics.append({
            "metric_name": metric["metric_name"],
            "value": metric["value"],
            "unit": metric.get("unit", ""),
            "confidence": metric.get("confidence", 0),
            "trust_score": metric.get("trust_score", {"grade": "N/A", "score": 0}),
            "drift": metric.get("drift", {"flag": "neutral", "z_score": 0}),
            "explainability": metric.get("explainability", {}),
            "source_provenance": metric.get("source_provenance", {})
        })
    
    # Build company block
    company_block = {
        "name": company.get("name"),
        "sector": company.get("sector"),
        "industry": company.get("industry"),
        "about": company.get("about", "")
    }
    
    # Build shareholding block
    shareholding_block = { "status": "unavailable", "summary": {}, "insights": [] }
    if ownership:
        # Extract from summary key or top level props
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
    
    # Handle last_updated which might be string or datetime
    last_updated = company.get("last_updated")
    if isinstance(last_updated, str):
        scraped_at = last_updated
    elif hasattr(last_updated, "isoformat"):
        scraped_at = last_updated.isoformat()
    else:
        scraped_at = datetime.now(timezone.utc).isoformat()

    # Build metadata
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
    
    # Build reliability block (Phase 24)
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
    
    # Simple staleness check for financials (heuristic)
    # In a full impl we'd check against ingestion timestamp in trust_report
    is_stale = False
    generated_at = trust_report.get("generated_at") if trust_report else None
    if generated_at:
        try:
            if isinstance(generated_at, str):
                gen_dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            else:
                gen_dt = generated_at
            
            days_old = (datetime.now(timezone.utc) - gen_dt).days
            if days_old > 365: # Financials block stale after 1 year
                is_stale = True
        except:
            pass

    # Build final response
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


@router.get("/indices/{index_name}/constituents")
async def get_index_constituents_mongo(index_name: str):
    """Get constituent symbols and basic metadata for an index from MongoDB."""
    symbols = get_constituents(index_name)
    if not symbols:
        raise HTTPException(status_code=404, detail=f"Index {index_name} not found")
    
    col = get_companies_col()
    cursor = col.find({"symbol": {"$in": symbols}}, {"symbol": 1, "name": 1, "sector": 1})
    
    results = []
    async for doc in cursor:
        results.append({
            "symbol": doc.get("symbol"),
            "name": doc.get("name") or doc.get("symbol"),
            "sector": doc.get("sector") or "Market Weighted"
        })
        
    return {
        "index": index_name.upper(),
        "count": len(results),
        "constituents": results
    }


@router.get("/coverage")
async def list_coverage_mongo():
    """Summarize data coverage across all processed companies in MongoDB."""
    companies = await mongo_repo.get_all_companies()
    
    # In a real app we'd compute this properly, for now just summarize what we have
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
