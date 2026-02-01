"""
MongoDB Repository - Data Access Layer
# Force Rebuild: Fix count_companies signature mismatch


This module provides async methods for interacting with MongoDB collections.
All database operations should go through this repository.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging
import re

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
        """Get all symbols from database"""
        cursor = self._companies.find({"symbol": {"$not": {"$regex": "^--"}}}, {"symbol": 1})
        symbols = [doc.get("symbol") async for doc in cursor if doc.get("symbol")]
        return sorted(symbols)
    
    async def get_all_companies(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Get companies with basic details. Efficient sorting, paging and filtering.
        Using **kwargs for maximum flexibility and stability.
        """
        skip = kwargs.get('skip', 0)
        limit = kwargs.get('limit', 50)
        sort_by = kwargs.get('sort_by', 'symbol')
        order = kwargs.get('order', 1)
        sector = kwargs.get('sector')
        search_query = kwargs.get('q')
        min_market_cap = kwargs.get('min_market_cap')
        max_market_cap = kwargs.get('max_market_cap')
        min_pe = kwargs.get('min_pe')
        max_pe = kwargs.get('max_pe')
        min_roe = kwargs.get('min_roe')

        # Complex query builder
        query = {"symbol": {"$not": {"$regex": "^--"}}}
        
        filters = []
        
        if sector and sector != "all":
            # Inclusive match: look in root 'sector' OR inside the legacy Fundametrics blob
            regex = {"$regex": f"^{re.escape(sector)}$", "$options": "i"}
            filters.append({"$or": [
                {"sector": regex},
                {"fundametrics_response.company.sector": regex}
            ]})

        if search_query:
            # Search in symbol and name (Inclusive across root and legacy paths)
            regex = {"$regex": re.escape(search_query), "$options": "i"}
            filters.append({"$or": [
                {"symbol": regex},
                {"name": regex},
                {"snapshot.name": regex},
                {"fundametrics_response.company.name": regex}
            ]})
            
        if filters:
            if len(filters) == 1:
                query.update(filters[0])
            else:
                query["$and"] = filters
            
        # Range filters on snapshot fields
        if min_market_cap is not None or max_market_cap is not None:
            query["snapshot.marketCap"] = {}
            if min_market_cap is not None: query["snapshot.marketCap"]["$gte"] = min_market_cap
            if max_market_cap is not None: query["snapshot.marketCap"]["$lte"] = max_market_cap
            
        if min_pe is not None or max_pe is not None:
            query["snapshot.pe"] = {}
            if min_pe is not None: query["snapshot.pe"]["$gte"] = min_pe
            if max_pe is not None: query["snapshot.pe"]["$lte"] = max_pe
            
        if min_roe is not None:
            query["snapshot.roe"] = {"$gte": min_roe}

        # Mapping for short-hand sort keys used by frontend
        sort_map = {
            "symbol": "symbol",
            "name": "name",
            "marketCap": "snapshot.marketCap",
            "pe": "snapshot.pe",
            "roe": "snapshot.roe",
            "roce": "snapshot.roce"
        }
        
        mongo_sort_key = sort_map.get(sort_by, sort_by)
        
        # Phase 25 Refinement: Priority sorting (e.g. NIFTY 50 first)
        if sort_by in ["name", "symbol"] and order == 1:
            sort_spec = [("snapshot.priority", -1), ("snapshot.marketCap", -1), ("name", 1)]
        else:
            sort_spec = [(mongo_sort_key, order)]

        cursor = self._companies.find(
            query,
            {
                "symbol": 1, "name": 1, "sector": 1, "industry": 1, "snapshot": 1,
                "fundametrics_response.company": 1,
                "fundametrics_response.fundametrics_metrics": 1,
                "fundametrics_response.metrics.values": 1
            }
        ).sort(sort_spec).skip(skip).limit(limit).allow_disk_use(True)
        
        return await self._format_company_list(cursor)
    
    async def count_companies(self, **kwargs) -> int:
        """
        Count total companies matching the given filters.
        Using **kwargs for maximum flexibility and stability.
        """
        sector = kwargs.get('sector')
        search_query = kwargs.get('q')
        min_market_cap = kwargs.get('min_market_cap')
        max_market_cap = kwargs.get('max_market_cap')
        min_pe = kwargs.get('min_pe')
        max_pe = kwargs.get('max_pe')
        min_roe = kwargs.get('min_roe')

        query = {"symbol": {"$not": {"$regex": "^--"}}}
        
        filters = []
        
        if sector and sector != "all":
            # Inclusive match: look in root 'sector' OR inside the legacy Fundametrics blob
            regex = {"$regex": f"^{re.escape(sector)}$", "$options": "i"}
            filters.append({"$or": [
                {"sector": regex},
                {"fundametrics_response.company.sector": regex}
            ]})

        if search_query:
            # Search in symbol and name (Inclusive across root and legacy paths)
            regex = {"$regex": re.escape(search_query), "$options": "i"}
            filters.append({"$or": [
                {"symbol": regex},
                {"name": regex},
                {"snapshot.name": regex},
                {"fundametrics_response.company.name": regex}
            ]})
            
        if filters:
            if len(filters) == 1:
                query.update(filters[0])
            else:
                query["$and"] = filters
            
        # Range filters on snapshot fields
        if min_market_cap is not None or max_market_cap is not None:
            # Note: Numerical filters still rely on the 'snapshot' optimizations.
            # Running the backfill script is recommended to enable these for all 2000+ companies.
            query["snapshot.marketCap"] = {}
            if min_market_cap is not None: query["snapshot.marketCap"]["$gte"] = min_market_cap
            if max_market_cap is not None: query["snapshot.marketCap"]["$lte"] = max_market_cap
            
        if min_pe is not None or max_pe is not None:
            query["snapshot.pe"] = {}
            if min_pe is not None: query["snapshot.pe"]["$gte"] = min_pe
            if max_pe is not None: query["snapshot.pe"]["$lte"] = max_pe
            
        if min_roe is not None:
            query["snapshot.roe"] = {"$gte": min_roe}
        
        return await self._companies.count_documents(query)

    async def get_companies_detail(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Get details for a specific list of symbols
        """
        companies = get_companies_col()
        cursor = companies.find({"symbol": {"$in": symbols}}, {
            "symbol": 1, "name": 1, "sector": 1, "industry": 1, "snapshot": 1,
            "fundametrics_response.company": 1,
            "fundametrics_response.fundametrics_metrics": 1,
            "fundametrics_response.metrics.values": 1,
            "fundametrics_response.metrics.ratios": 1
        })
        
        return await self._format_company_list(cursor)

    async def _format_company_list(self, cursor) -> List[Dict[str, Any]]:
        results = []
        async for doc in cursor:
            # High-speed path: Using the new 'snapshot' block
            if "snapshot" in doc and doc["snapshot"]:
                snap = doc["snapshot"]
                results.append({
                    "symbol": snap.get("symbol") or doc.get("symbol"),
                    "name": snap.get("name") or doc.get("name"),
                    "sector": snap.get("sector") or doc.get("sector") or "General",
                    "industry": snap.get("industry") or doc.get("industry") or "General",
                    "marketCap": snap.get("marketCap"),
                    "currentPrice": snap.get("currentPrice"),
                    "changePercent": snap.get("changePercent") or 0.0,
                    "priority": snap.get("priority") or 0,
                    "pe": snap.get("pe"),
                    "roe": snap.get("roe"),
                    "roce": snap.get("roce"),
                })
                continue

            # Fallback path: Slow extraction from Fundametrics Response
            fr = doc.get("fundametrics_response") or {}
            ui_metrics = fr.get("fundametrics_metrics") or []
            fr_comp = fr.get("company") or {}
            
            # Build lookup with safety
            m_map = {}
            if isinstance(ui_metrics, list):
                m_map = {m.get("metric_name"): m.get("value") for m in ui_metrics if isinstance(m, dict) and m.get("metric_name")}
            
            name = doc.get("name") or fr_comp.get("name") or doc.get("symbol") or "Unknown"
            if name == "Unknown": name = doc.get("symbol")
            if doc.get("symbol") == "ZOMATO": name = "Eternal Ltd"
            
            def get_latest(val):
                if isinstance(val, list) and len(val) > 0:
                    last = val[-1]
                    if isinstance(last, dict): return last.get("value")
                return val

            # Robust extraction: Try list metrics, then direct fields
            mcap = get_latest(m_map.get("Market Cap") or m_map.get("Market_Cap")) or doc.get("market_cap")
            price = get_latest(m_map.get("Current Price") or m_map.get("Price")) or doc.get("price") or doc.get("current_price")
            pe = get_latest(m_map.get("pe_ratio") or m_map.get("p/e_ratio") or m_map.get("PE Ratio") or m_map.get("pe"))
            roe = get_latest(m_map.get("roe") or m_map.get("return_on_equity") or m_map.get("ROE") or m_map.get("roe"))
            roce = get_latest(m_map.get("roce") or m_map.get("return_on_capital_employed") or m_map.get("ROCE") or m_map.get("roce"))

            # Emergency Fallback (Phase 15/25): Try deep metrics blob if still missing
            deep_metrics = fr.get("metrics", {}).get("values", [])
            if isinstance(deep_metrics, list) and (not mcap or not price or not roe or not pe or not roce):
                for m in deep_metrics:
                    m_key = m.get("metric") or ""
                    m_val = get_latest(m.get("value"))
                    if not mcap and m_key in ["Market Cap", "Market_Cap", "MCAP"]: mcap = m_val
                    if not price and m_key in ["Price", "Current Price"]: price = m_val
                    if not pe and m_key in ["PE Ratio", "P/E Ratio", "P/E"]: pe = m_val
                    if not roe and m_key in ["ROE", "Return on Equity"]: roe = m_val
                    if not roce and m_key in ["ROCE", "Return on Capital Employed"]: roce = m_val

            results.append({
                "symbol": doc.get("symbol"),
                "name": name,
                "sector": doc.get("sector") or fr_comp.get("sector") or "General",
                "industry": doc.get("industry") or fr_comp.get("industry") or "General",
                "marketCap": mcap,
                "currentPrice": price,
                "changePercent": m_map.get("Change Percent") or m_map.get("Change_Percent") or 0.0,
                "priority": 0, # Fallback path is always non-priority
                "pe": m_map.get("pe_ratio") or m_map.get("p/e_ratio") or m_map.get("PE Ratio") or m_map.get("pe"),
                "roe": m_map.get("roe") or m_map.get("return_on_equity") or m_map.get("ROE") or m_map.get("roe"),
                "roce": m_map.get("roce") or m_map.get("return_on_capital_employed") or m_map.get("ROCE") or m_map.get("roce"),
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

    
    async def run_backfill(self) -> Dict[str, Any]:
        """
        Promotes nested data to root and snapshot fields for all companies.
        Ensures numerical filters work correctly.
        """
        col = get_companies_col()
        cursor = col.find({})
        
        count = 0
        updated = 0
        
        def to_float(val):
            if val is None: return None
            try:
                # Handle % and ,
                if isinstance(val, str):
                    val = val.replace("%", "").replace(",", "").strip()
                return float(val)
            except:
                return None

        async for doc in cursor:
            count += 1
            symbol = doc.get("symbol")
            if not symbol: continue
            
            fr = doc.get("fundametrics_response") or {}
            ui_metrics = fr.get("fundametrics_metrics") or []
            fr_comp = fr.get("company") or {}
            
            # Build metric map
            m_map = {}
            if isinstance(ui_metrics, list):
                m_map = {m.get("metric_name"): m.get("value") for m in ui_metrics if isinstance(m, dict) and m.get("metric_name")}
            
            def get_latest(val):
                if isinstance(val, list) and len(val) > 0:
                    last = val[-1]
                    if isinstance(last, dict): return last.get("value")
                return val

            # Robust extraction: Try list metrics, then direct fields
            mcap = get_latest(m_map.get("Market Cap") or m_map.get("Market_Cap")) or doc.get("market_cap")
            price = get_latest(m_map.get("Current Price") or m_map.get("Price")) or doc.get("price") or doc.get("current_price")
            pe = get_latest(m_map.get("pe_ratio") or m_map.get("p/e_ratio") or m_map.get("PE Ratio") or m_map.get("pe"))
            roe = get_latest(m_map.get("roe") or m_map.get("return_on_equity") or m_map.get("ROE") or m_map.get("roe"))
            roce = get_latest(m_map.get("roce") or m_map.get("return_on_capital_employed") or m_map.get("ROCE") or m_map.get("roce"))

            # Emergency Fallback (Phase 15/25): Try deep metrics blob if still missing
            deep_metrics = fr.get("metrics", {}).get("values", [])
            if isinstance(deep_metrics, list) and (not mcap or not price or not roe or not pe or not roce):
                for m in deep_metrics:
                    m_key = m.get("metric") or ""
                    m_val = get_latest(m.get("value"))
                    if not mcap and m_key in ["Market Cap", "Market_Cap", "MCAP"]: mcap = m_val
                    if not price and m_key in ["Price", "Current Price"]: price = m_val
                    if not pe and m_key in ["PE Ratio", "P/E Ratio", "P/E"]: pe = m_val
                    if not roe and m_key in ["ROE", "Return on Equity"]: roe = m_val
                    if not roce and m_key in ["ROCE", "Return on Capital Employed"]: roce = m_val

            # Build snapshot with FLOAT conversion
            snapshot = {
                "symbol": symbol,
                "name": doc.get("name") or fr_comp.get("name") or symbol,
                "sector": doc.get("sector") or fr_comp.get("sector") or "General",
                "industry": doc.get("industry") or fr_comp.get("industry") or "General",
                "marketCap": to_float(mcap),
                "currentPrice": to_float(price),
                "pe": to_float(pe),
                "roe": to_float(roe),
                "roce": to_float(roce),
                "priority": doc.get("snapshot", {}).get("priority") or 0
            }
            
            # Use original priority if exists and non-zero
            if doc.get("priority"):
                 snapshot["priority"] = doc.get("priority")
            
            # Also promote sector and name to root for faster filtering
            update_payload = {
                "snapshot": snapshot,
                "sector": snapshot["sector"],
                "name": snapshot["name"]
            }
            
            await col.update_one({"_id": doc["_id"]}, {"$set": update_payload})
            updated += 1
            
        return {"total_scanned": count, "updated": updated}

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
