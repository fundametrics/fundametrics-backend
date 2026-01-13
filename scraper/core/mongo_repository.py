"""
MongoDB Repository - Data Access Layer

This module provides async methods for interacting with MongoDB collections.
All database operations should go through this repository.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging

from scraper.core.db import (
    get_companies_col,
    get_financials_annual_col,
    get_financials_quarterly_col,
    get_metrics_col,
    get_ownership_col,
    get_trust_metadata_col,
    get_trust_reports_col
)

logger = logging.getLogger(__name__)


class MongoRepository:
    def __init__(self, db):
        self._db = db
        self._companies = self._db["companies"]
    """MongoDB data access layer for Fundametrics"""
    
    # ==================== COMPANIES ====================
    
    async def get_all_symbols(self) -> List[str]:
        """
        Get all company symbols from database
        
        Returns:
            List of symbols (e.g., ['RELIANCE', 'TCS', 'INFY'])
        """
        companies = get_companies_col()
        cursor = companies.find({"symbol": {"$not": {"$regex": "^--"}}}, {"symbol": 1})
        symbols = [doc.get("symbol") async for doc in cursor if doc.get("symbol")]
        return sorted(symbols)
    
    async def get_all_companies(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all companies with basic details (Screener-style list)
        """
        companies = get_companies_col()
        cursor = companies.find({"symbol": {"$not": {"$regex": "^--"}}}, {
            "symbol": 1, "name": 1, "sector": 1, "industry": 1,
            "fundametrics_response.fundametrics_metrics": 1,
            "fundametrics_response.metrics.values": 1,
            "fundametrics_response.metrics.ratios": 1
        }).sort("symbol", 1).skip(skip).limit(limit)
        
        return await self._format_company_list(cursor)

    async def get_companies_detail(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Get details for a specific list of symbols
        """
        companies = get_companies_col()
        cursor = companies.find({"symbol": {"$in": symbols}}, {
            "symbol": 1, "name": 1, "sector": 1, "industry": 1,
            "fundametrics_response.fundametrics_metrics": 1,
            "fundametrics_response.metrics.values": 1,
            "fundametrics_response.metrics.ratios": 1
        })
        
        return await self._format_company_list(cursor)

    async def _format_company_list(self, cursor) -> List[Dict[str, Any]]:
        results = []
        async for doc in cursor:
            fr = doc.get("fundametrics_response", {})
            # UI logic list
            ui_metrics = fr.get("fundametrics_metrics", [])
            # Builder format dicts
            metrics_block = fr.get("metrics", {})
            builder_values = metrics_block.get("values", {})
            builder_ratios = metrics_block.get("ratios", {})
            
            if doc.get("symbol") == "RELIANCE":
                logger.debug(f"RELIANCE debug: ui={len(ui_metrics)} values={len(builder_values)} ratios={len(builder_ratios)}")
            
            def get_val(name_list):
                # 1. Check UI list format
                for name in name_list:
                    for m in ui_metrics:
                        if m.get("metric_name") == name:
                            return m.get("value")
                
                # 2. Check Builder dict format (prefix with fundametrics_ usually)
                for name in name_list:
                    # check keys directly
                    if name in builder_values:
                        v = builder_values[name]
                        return v.get("value") if isinstance(v, dict) else v
                    if name in builder_ratios:
                        v = builder_ratios[name]
                        return v.get("value") if isinstance(v, dict) else v
                    
                    # check common prefixes if not found
                    if not name.startswith("fundametrics_"):
                        low_name = name.lower().replace(' ', '_')
                        prefixed = f"fundametrics_{low_name}"
                        for p in [prefixed, low_name]:
                            if p in builder_values:
                                v = builder_values[p]
                                return v.get("value") if isinstance(v, dict) else v
                            if p in builder_ratios:
                                v = builder_ratios[p]
                                return v.get("value") if isinstance(v, dict) else v

                # 3. Fallback: Check Raw Financials Tables (Latest Period)
                financials = fr.get("financials", {})
                # Search ratios_table and ratios block
                for table_key in ["ratios_table", "ratios", "income_statement"]:
                    table = financials.get(table_key, {})
                    if not table: continue
                    # Get periods sorted latest first
                    periods = sorted(table.keys(), reverse=True)
                    for p in periods:
                        row = table[p]
                        if not isinstance(row, dict): continue
                        for name in name_list:
                            low_name = name.lower().replace(' ', '_')
                            for k in [name, low_name, f"fundametrics_{low_name}"]:
                                if k in row:
                                    v = row[k]
                                    val = v.get("value") if isinstance(v, dict) else v
                                    if val is not None: return val
                return None

            # Zomato Name Fix & General Fallback
            name = doc.get("name")
            symbol = doc.get("symbol", str(doc.get("_id")))
            
            if not name or name == "Unknown":
                name = symbol
                
            if symbol == "ZOMATO":
                name = "Eternal Ltd"
            
            # Optimization: Build simpler lookup map once
            metric_lookup = {}
            
            # 1. From UI Metrics (Preferred)
            for m in ui_metrics:
                if m.get("metric_name"):
                    metric_lookup[m["metric_name"]] = m.get("value")
                    
            # 2. From Builder Values & Ratios (Fallback & Augment)
            if not metric_lookup:
                # Merge values and ratios for lookup
                combined = {**builder_values, **builder_ratios}
                for k, v in combined.items():
                    val = v.get("value") if isinstance(v, dict) else v
                    metric_lookup[k] = val
                    metric_lookup[k.lower()] = val # heuristic
                    # also allow checking without fundametrics_ prefix
                    if k.startswith("fundametrics_"):
                        raw_k = k.replace("fundametrics_", "")
                        if raw_k not in metric_lookup:
                            metric_lookup[raw_k] = val
                            metric_lookup[raw_k.replace("_", " ")] = val
            
            # Debug Zomato/Eternal
            if doc.get("symbol") == "ZOMATO":
                keys_found = list(metric_lookup.keys())
                logger.debug(f"ZOMATO Metrics keys: {keys_found}")

            def quick_get(keys):
                for k in keys:
                    if k in metric_lookup: return metric_lookup[k]
                return None

            # Sector/Industry Fallbacks (Fix for '20 Microns' consistency issue)
            fr_comp = fr.get("company", {})
            sector = doc.get("sector")
            if not sector or sector == "Unknown":
                sector = fr_comp.get("sector") or "General"
                
            industry = doc.get("industry")
            if not industry or industry == "Unknown":
                industry = fr_comp.get("industry") or "General"

            results.append({
                "symbol": doc.get("symbol", str(doc.get("_id"))),
                "name": name,
                "sector": sector,
                "industry": industry,
                "marketCap": quick_get(["Market Cap", "fundametrics_market_cap", "market_cap"]),
                "currentPrice": quick_get(["Current Price", "fundametrics_current_price", "current_price", "Price"]),
                "pe": quick_get(["Pe Ratio", "P/E Ratio", "fundametrics_pe_ratio", "pe_ratio", "price_to_earnings", "Stock P/E"]),
                "roe": quick_get(["ROE", "Return On Equity", "fundametrics_return_on_equity", "roe", "return_on_equity"]),
                "roce": quick_get(["ROCE", "Return On Capital Employed", "fundametrics_return_on_capital_employed", "roce", "return_on_capital_employed"]),
                "debt": quick_get(["Debt To Equity", "Total Debt", "fundametrics_debt_to_equity", "debt_to_equity"])
            })
        return results
    
    async def get_company(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get company profile by symbol
        
        Args:
            symbol: Company symbol (e.g., 'RELIANCE')
            
        Returns:
            Company document or None if not found
        """
        companies = get_companies_col()
        doc = await companies.find_one({"symbol": symbol.upper()})
        
        if doc and doc.get("symbol") == "ZOMATO":
            doc["name"] = "Eternal Ltd"
            
        return doc
    
    async def search_companies(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Search companies by name or symbol
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List of matching company documents
        """
        companies = get_companies_col()
        results = []
        query_upper = query.upper()
        
        # 1. Exact symbol match (highest priority)
        exact_match = await companies.find_one({"symbol": query_upper})
        if exact_match:
            results.append(exact_match)
        
        # 2. Symbol prefix match
        cursor = companies.find(
            {"symbol": {"$regex": f"^{query_upper}", "$options": "i"}}
        ).limit(limit)
        async for doc in cursor:
            # Avoid duplicates (ObjectId comparison works here)
            if doc["_id"] not in [r["_id"] for r in results]:
                results.append(doc)
        
        # 3. Name prefix/contains match (good for partial typing)
        if len(results) < limit:
            cursor = companies.find(
                {"name": {"$regex": query, "$options": "i"}}
            ).limit(limit - len(results))
            async for doc in cursor:
                if doc["_id"] not in [r["_id"] for r in results]:
                    results.append(doc)

        # 4. Text search on name (fallback for complex queries)
        if len(results) < limit:
            cursor = companies.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit - len(results))
            
            async for doc in cursor:
                if doc["_id"] not in [r["_id"] for r in results]:
                    results.append(doc)
        
        # Zomato Fix for Search Results
        for r in results:
            if r.get("symbol") == "ZOMATO":
                r["name"] = "Eternal Ltd"

        return results[:limit]
    
    async def upsert_company(self, symbol: str, payload: dict):
        await self._companies.update_one(
            {"symbol": symbol},
            {"$set": payload},
            upsert=True
        )
        logger.info(f"Upserted company: {symbol}")
    
    # ==================== FINANCIALS ====================
    
    async def get_financials_annual(
        self, 
        symbol: str, 
        statement_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get annual financial statements for a symbol
        
        Args:
            symbol: Company symbol
            statement_type: Optional filter ('income_statement', 'balance_sheet', 'cash_flow')
            
        Returns:
            List of financial statement documents, sorted by year (descending)
        """
        financials = get_financials_annual_col()
        query = {"symbol": symbol.upper()}
        if statement_type:
            query["statement_type"] = statement_type
        
        cursor = financials.find(query).sort("year", -1)
        return [doc async for doc in cursor]
    
    async def upsert_financials_annual(
        self,
        symbol: str,
        year: str,
        statement_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Insert or update annual financial statement
        
        Args:
            symbol: Company symbol
            year: Period (e.g., 'Mar 2024')
            statement_type: 'income_statement', 'balance_sheet', or 'cash_flow'
            data: Financial data dictionary
            metadata: Optional metadata (source, scraped_at, etc.)
        """
        financials = get_financials_annual_col()
        
        doc = {
            "symbol": symbol.upper(),
            "year": year,
            "period_type": "annual",
            "statement_type": statement_type,
            "data": data,
            "metadata": metadata or {
                "source": "screener.in",
                "scraped_at": datetime.now(timezone.utc)
            }
        }
        
        await financials.update_one(
            {
                "symbol": symbol.upper(),
                "year": year,
                "statement_type": statement_type
            },
            {"$set": doc},
            upsert=True
        )
        logger.debug(f"Upserted {statement_type} for {symbol} ({year})")
    
    # ==================== METRICS ====================
    
    async def get_metrics(
        self,
        symbol: str,
        metric_name: Optional[str] = None,
        period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get metrics for a symbol
        
        Args:
            symbol: Company symbol
            metric_name: Optional filter by metric name
            period: Optional filter by period
            
        Returns:
            List of metric documents
        """
        metrics = get_metrics_col()
        query = {"symbol": symbol.upper()}
        
        if metric_name:
            query["metric_name"] = metric_name
        if period:
            query["period"] = period
        
        cursor = metrics.find(query).sort("period", -1)
        return [doc async for doc in cursor]
    
    async def upsert_metric(
        self,
        symbol: str,
        period: str,
        metric_name: str,
        value: Any,
        unit: str = "",
        confidence: float = 0.0,
        trust_score: Optional[Dict] = None,
        drift: Optional[Dict] = None,
        explainability: Optional[Dict] = None,
        source_provenance: Optional[Dict] = None
    ):
        """
        Insert or update a metric
        
        Args:
            symbol: Company symbol
            period: Period (e.g., 'Mar 2024')
            metric_name: Metric name (e.g., 'ROE')
            value: Metric value
            unit: Unit (e.g., '%', 'Cr')
            confidence: Confidence score (0-1)
            trust_score: Trust score dict
            drift: Drift detection dict
            explainability: Explainability metadata
            source_provenance: Source provenance metadata
        """
        metrics = get_metrics_col()
        
        doc = {
            "symbol": symbol.upper(),
            "period": period,
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "confidence": confidence,
            "trust_score": trust_score or {"grade": "N/A", "score": 0},
            "drift": drift or {"flag": "neutral", "z_score": 0, "magnitude": 0},
            "explainability": explainability or {},
            "source_provenance": source_provenance or {}
        }
        
        await metrics.update_one(
            {
                "symbol": symbol.upper(),
                "period": period,
                "metric_name": metric_name
            },
            {"$set": doc},
            upsert=True
        )
        logger.debug(f"Upserted metric {metric_name} for {symbol} ({period})")
    
    # ==================== OWNERSHIP ====================
    
    async def get_ownership(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest ownership data for a symbol
        
        Args:
            symbol: Company symbol
            
        Returns:
            Latest ownership document or None
        """
        ownership = get_ownership_col()
        return await ownership.find_one(
            {"symbol": symbol.upper()},
            sort=[("quarter", -1)]
        )
    
    async def upsert_ownership(
        self,
        symbol: str,
        quarter: str,
        summary: Dict[str, float],
        history: Optional[List[Dict]] = None,
        insights: Optional[List[Dict]] = None
    ):
        """
        Insert or update ownership data
        
        Args:
            symbol: Company symbol
            quarter: Quarter (e.g., 'Q2 FY25')
            summary: Ownership summary dict
            history: Optional historical data
            insights: Optional insights list
        """
        ownership = get_ownership_col()
        
        doc = {
            "symbol": symbol.upper(),
            "quarter": quarter,
            "summary": summary,
            "history": history or [],
            "insights": insights or []
        }
        
        await ownership.update_one(
            {"symbol": symbol.upper(), "quarter": quarter},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Upserted ownership for {symbol} ({quarter})")
    
    # ==================== TRUST METADATA ====================
    
    async def upsert_trust_metadata(
        self,
        symbol: str,
        run_id: str,
        coverage: Dict[str, Any],
        warnings: List[Dict] = None,
        data_sources: Dict[str, str] = None
    ):
        """
        Insert or update trust metadata
        
        Args:
            symbol: Company symbol
            run_id: Ingestion run ID
            coverage: Coverage data
            warnings: Optional warnings list
            data_sources: Optional data sources dict
        """
        trust_metadata = get_trust_metadata_col()
        
        doc = {
            "symbol": symbol.upper(),
            "run_id": run_id,
            "run_timestamp": datetime.now(timezone.utc),
            "coverage": coverage,
            "warnings": warnings or [],
            "data_sources": data_sources or {}
        }
        
        await trust_metadata.update_one(
            {"symbol": symbol.upper(), "run_id": run_id},
            {"$set": doc},
            upsert=True
        )
        logger.info(f"Upserted trust metadata for {symbol} (run: {run_id})")
    
    async def get_peers(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get peer companies in the same sector
        
        Args:
            symbol: Original company symbol
            limit: Max peers to return
            
        Returns:
            List of peer company dicts
        """
        companies_col = get_companies_col()
        
        # 1. Get original company sector
        original = await companies_col.find_one({"symbol": symbol.upper()}, {"sector": 1})
        if not original or not original.get("sector"):
            return []
            
        sector = original["sector"]
        
        # 2. Find other companies in same sector
        cursor = companies_col.find(
            {
                "sector": sector,
                "symbol": {"$ne": symbol.upper()}
            },
            {
                "symbol": 1, "name": 1, "sector": 1,
                "fundametrics_response.metrics.values": 1,
                "fundametrics_response.metrics.ratios": 1,
                "fundametrics_response.fundametrics_metrics": 1
            }
        ).limit(limit)
        
        peers = []
        async for doc in cursor:
            # We reuse the logic from get_all_companies to extract PE, MCAP etc.
            # For simplicity here, we'll just extract what we need for SmartComparison
            fr = doc.get("fundametrics_response", {})
            metrics_values = fr.get("metrics", {}).get("values", {})
            metrics_ratios = fr.get("metrics", {}).get("ratios", {})
            ui_metrics = fr.get("fundametrics_metrics", [])
            
            def find_metric(keys):
                for k in keys:
                    if k in metrics_values: return metrics_values[k].get("value")
                    if k in metrics_ratios: return metrics_ratios[k].get("value")
                    for m in ui_metrics:
                        if m.get("metric_name") == k: return m.get("value")
                return None

            peers.append({
                "symbol": doc.get("symbol"),
                "name": doc.get("name"),
                "pe": find_metric(["fundametrics_pe_ratio", "pe_ratio", "P/E Ratio"]),
                "market_cap": find_metric(["fundametrics_market_cap", "market_cap", "Market Cap"]),
                "roe": find_metric(["fundametrics_return_on_equity", "roe", "ROE"]),
                "trust_grade": "A", # Placeholder or derived from metadata
                "confidence_tier": 1 # Placeholder
            })
            
        return peers

    # ==================== UTILITY ====================
    
    async def get_stats(self) -> Dict[str, int]:
        """
        Get database statistics
        
        Returns:
            Dict with collection counts
        """
        return {
            "companies": await get_companies_col().count_documents({}),
            "financials_annual": await get_financials_annual_col().count_documents({}),
            "metrics": await get_metrics_col().count_documents({}),
            "ownership": await get_ownership_col().count_documents({})
        }
    async def company_exists(self, symbol: str) -> bool:
        companies = get_companies_col()
        return await companies.count_documents({"_id": symbol.upper()}, limit=1) > 0

    async def count_companies(self) -> int:
        return await get_companies_col().count_documents({})

    
    # ==================== TRUST & RELIABILITY (Phase 24) ====================
    
    async def upsert_trust_report(self, report: dict):
        """
        Store or update reliability metadata for a company.
        """
        col = get_trust_reports_col()
        await col.update_one(
            {"symbol": report["symbol"]},
            {"$set": report},
            upsert=True
        )
        logger.info(f"✅ Reliability report persisted for {report['symbol']}")

    async def get_trust_report(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the latest reliability report for a symbol.
        """
        col = get_trust_reports_col()
        return await col.find_one({"symbol": symbol.upper()})
