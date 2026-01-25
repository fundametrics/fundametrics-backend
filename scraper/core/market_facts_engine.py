from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass

from scraper.core.fetcher import Fetcher
from scraper.utils.logger import get_logger


@dataclass(frozen=True)
class MarketFacts:
    """Immutable market facts data structure."""
    current_price: Optional[float]
    price_currency: str
    price_delay_minutes: int
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    shares_outstanding: Optional[float]
    market_cap: Optional[float]
    market_cap_currency: str
    last_updated: datetime


class MarketFactsEngine:
    """
    Read-only MarketFactsEngine for fetching delayed market data.
    
    This engine only fetches factual market data from public sources:
    - Delayed price information
    - 52-week high/low ranges
    - Shares outstanding
    - Internally computed market cap
    
    No advisory or predictive fields are exposed.
    """
    
    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher = fetcher or Fetcher()
        self._log = get_logger(__name__)
        
        # Standard delay disclaimer for delayed market data
        self._delay_disclaimer = (
            "Market data is delayed by at least 15-20 minutes as per exchange regulations. "
            "This data is for informational purposes only and should not be used for trading decisions."
        )
        
        # Standard data source disclaimer
        self._source_disclaimer = (
            "Market data sourced from public financial information providers. "
            "Accuracy cannot be guaranteed and data may be subject to corrections."
        )

    async def fetch_market_facts(self, symbol: str) -> MarketFacts:
        """
        Fetch market facts for a given symbol using a single batch-efficient request.
        """
        # NSE symbols need .NS suffix for Yahoo
        yahoo_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.endswith(".BO") else symbol
        
        self._log.info("Fetching market facts for {}", symbol)
        
        # Optimized: Fetch ALL data in ONE request using fetch_batch_prices
        batch_results = await self.fetch_batch_prices([yahoo_symbol])
        data = batch_results[0] if batch_results else {}
        
        current_price = data.get("price")
        high_52w = data.get("fifty_two_week_high")
        low_52w = data.get("fifty_two_week_low")
        shares_outstanding = data.get("shares_outstanding")
        
        # Compute market cap internally
        market_cap = self._compute_market_cap(current_price, shares_outstanding)
        
        market_facts = MarketFacts(
            current_price=current_price,
            price_currency=data.get("currency", "INR"),
            price_delay_minutes=15,
            fifty_two_week_high=high_52w,
            fifty_two_week_low=low_52w,
            shares_outstanding=shares_outstanding,
            market_cap=market_cap,
            market_cap_currency=data.get("currency", "INR"),
            last_updated=datetime.now(timezone.utc)
        )
        
        self._log.info(
            "Market facts retrieved for {}: price={}, market_cap={}",
            symbol, current_price, market_cap
        )
        return market_facts

    def build_market_block(self, market_facts: MarketFacts) -> Dict[str, Any]:
        """
        Build market data block with metadata.
        
        Args:
            market_facts: Market facts data structure
            
        Returns:
            Dict containing market data block with source, delay, and disclaimer metadata
        """
        market_block = {
            "price": {
                "value": market_facts.current_price,
                "currency": market_facts.price_currency,
                "delay_minutes": market_facts.price_delay_minutes
            },
            "range_52_week": {
                "high": market_facts.fifty_two_week_high,
                "low": market_facts.fifty_two_week_low,
                "currency": market_facts.price_currency
            },
            "shares_outstanding": {
                "value": market_facts.shares_outstanding,
                "currency": "shares"
            },
            "market_cap": {
                "value": market_facts.market_cap,
                "currency": market_facts.market_cap_currency,
                "computed": "internal"
            },
            "metadata": {
                "source": "public_market_data",
                "last_updated": market_facts.last_updated.isoformat(),
                "delay_disclaimer": self._delay_disclaimer,
                "source_disclaimer": self._source_disclaimer,
                "data_type": "facts_only"
            }
        }
        
        return market_block

    async def _fetch_delayed_price(self, symbol: str) -> Dict[str, Any]:
        """Fetch delayed price data from Yahoo Finance."""
        # Fix: Normalize symbol by stripping existing suffixes first
        base_symbol = symbol.split('.')[0] if '.' in symbol and not symbol.startswith('^') else symbol
        
        # Index symbols (starting with ^) should be used as-is.
        # Stocks usually need .NS or .BO suffix.
        suffixes = [""] if base_symbol.startswith("^") else [".NS", ".BO"]
        for suffix in suffixes:
            try:
                import urllib.parse
                yahoo_symbol = f"{base_symbol}{suffix}" if suffix else base_symbol
                quoted_symbol = urllib.parse.quote(yahoo_symbol)
                # query2 is often more reliable/less throttled than query1
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{quoted_symbol}?interval=1d"
                
                # Use a specific short timeout for live market data (2.5s)
                response = await self._fetcher.fetch_json(url, timeout=2.5)
                
                if response and "chart" in response and response["chart"]["result"]:
                    result = response["chart"]["result"][0]
                    meta = result.get("meta", {})
                    
                    price = meta.get("regularMarketPrice")
                    if price is not None:
                        self._log.debug("Price found for {}: {}", yahoo_symbol, price)
                        return {
                            "current_price": float(price),
                            "delay_minutes": 15,
                            "currency": meta.get("currency", "INR"),
                            "timestamp": meta.get("regularMarketTime")
                        }
            except Exception as exc:
                self._log.warning("Yahoo fetch failed for {}{}: {}", base_symbol, suffix, exc)
                # If we timed out or failed, don't wait too long for the next suffix
                continue
                
        return {}

    async def _fetch_52_week_range(self, symbol: str) -> Dict[str, Any]:
        """Fetch 52-week high/low data from Yahoo Finance."""
        # Fix: Normalize symbol
        base_symbol = symbol.split('.')[0] if '.' in symbol and not symbol.startswith('^') else symbol
        try:
            yahoo_symbol = f"{base_symbol}.NS"
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d"
            response = await self._fetcher.fetch_json(url, timeout=3.0)
            
            if response and "chart" in response and response["chart"]["result"]:
                meta = response["chart"]["result"][0].get("meta", {})
                high = meta.get("fiftyTwoWeekHigh")
                low = meta.get("fiftyTwoWeekLow")
                
                if high is not None and low is not None:
                    return {
                        "fifty_two_week_high": float(high),
                        "fifty_two_week_low": float(low),
                        "currency": meta.get("currency", "INR")
                    }
        except Exception as exc:
            self._log.debug("Failed to fetch 52-week range for {}: {}", base_symbol, exc)
            
        return {}

    async def _fetch_shares_outstanding(self, symbol: str) -> Dict[str, Any]:
        """Fetch shares outstanding data."""
        return {}

    async def fetch_batch_prices(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        GHOST-MODE prioritized fetching. 
        Uses Chart API (v8) first as it's more resilient to cloud-IP blocks.
        """
        if not symbols:
            return []
            
        from scraper.utils.yahoo_session import YahooSession
        session = await YahooSession.get_instance()
        
        if session.is_in_quarantine():
            return [{} for _ in symbols]
            
        await session.refresh_if_needed()
        
        # GHOST-MODE: Try Chart API FIRST (Stealthiest)
        results_map = {}
        missing_symbols = []
        
        if len(symbols) <= 15:
            self._log.debug("Ghost-Mode: Attempting Chart API layer")
            tasks = [self._fetch_delayed_price(s) for s in symbols]
            chart_responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for sym, chart_data in zip(symbols, chart_responses):
                if isinstance(chart_data, dict) and chart_data.get("current_price"):
                    results_map[sym] = {
                        "price": chart_data["current_price"],
                        "change": 0, "change_percent": 0,
                        "symbol": sym, "currency": chart_data.get("currency", "INR")
                    }
                else:
                    missing_symbols.append(sym)
                    
            if not missing_symbols:
                self._log.info("✅ Success: Chart API Layer (Full Cache Update)")
                return [results_map[s] for s in symbols]

        # FALLBACK: Quote API for missing symbols or large batches
        batch_symbols = missing_symbols if missing_symbols else symbols
        subdomains = ["query2", "query1"]
        
        for sub in subdomains:
            # Ghost-Mode: Try Clean fetch first (less identifiable)
            for mode in ["clean", "session"]:
                try:
                    symbols_str = ",".join(batch_symbols)
                    url = f"https://{sub}.finance.yahoo.com/v7/finance/quote?symbols={symbols_str}"
                    
                    api_headers = session.get_headers({
                        "Accept": "application/json, text/plain, */*",
                        "Origin": "https://finance.yahoo.com"
                    })
                    
                    kwargs = {"timeout": 8.0, "headers": api_headers}
                    if mode == "session":
                        p = session.get_api_params()
                        c = session.get_cookies()
                        if p or c:
                            kwargs["params"] = p
                            kwargs["cookies"] = c
                        else: continue 
                    
                    response = await self._fetcher.fetch_json(url, **kwargs)
                    
                    if response and "quoteResponse" in response and response["quoteResponse"].get("result"):
                        results = response["quoteResponse"]["result"]
                        for r in results:
                            sym = r.get("symbol")
                            if sym:
                                results_map[sym] = {
                                    "price": r.get("regularMarketPrice"),
                                    "change": r.get("regularMarketChange"),
                                    "change_percent": r.get("regularMarketChangePercent"),
                                    "fifty_two_week_high": r.get("fiftyTwoWeekHigh"),
                                    "fifty_two_week_low": r.get("fiftyTwoWeekLow"),
                                    "shares_outstanding": r.get("sharesOutstanding"),
                                    "symbol": sym,
                                    "currency": r.get("currency", "INR")
                                }
                        
                        self._log.info(f"✅ Success: Quote API ({sub}/{mode})")
                        return [results_map.get(s, {}) for s in symbols]
                except Exception as e:
                    sc = getattr(e, 'status_code', None)
                    if sc == 401:
                        await session.clear_crumb()
                        if mode == "session": continue # Try clean mode immediately

                    if sc == 429 or "429" in str(e):
                        if sub == subdomains[-1] and mode == "session":
                            await session.trigger_quarantine(minutes=30)
                        continue 
                    continue

        return [results_map.get(s, {}) for s in symbols]

    async def fetch_index_price(self, index_symbol: str) -> Dict[str, Any]:
        """Fetch current price and change for an index (e.g., ^NSEI)."""
        # Optimized: delegates to batch fetcher for consistent behavior
        results = await self.fetch_batch_prices([index_symbol])
        return results[0] if results else {}

    def _compute_market_cap(self, price: Optional[float], shares: Optional[float]) -> Optional[float]:
        """
        Compute market cap internally from price and shares.
        
        Args:
            price: Current share price
            shares: Shares outstanding
            
        Returns:
            Market cap in crores (INR) or None if inputs invalid
        """
        if price is None or shares is None or price <= 0 or shares <= 0:
            return None
            
        # Compute market cap (price * shares) and convert to crores
        market_cap = price * shares / 10000000  # Convert to crores
        
        return round(market_cap, 2)

    def _extract_float(self, data: Union[Dict[str, Any], Exception], key: str, default: Optional[float] = None) -> Optional[float]:
        """Safely extract float value from data or exception."""
        if isinstance(data, Exception):
            return default
            
        if not isinstance(data, dict):
            return default
            
        value = data.get(key)
        if value is None:
            return default
            
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _extract_int(self, data: Union[Dict[str, Any], Exception], key: str, default: int = 0) -> int:
        """Safely extract integer value from data or exception."""
        if isinstance(data, Exception):
            return default
            
        if not isinstance(data, dict):
            return default
            
        value = data.get(key)
        if value is None:
            return default
            
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _extract_shares(self, data: Union[Dict[str, Any], Exception]) -> Optional[float]:
        """Safely extract shares outstanding value."""
        shares = self._extract_float(data, "shares_outstanding")
        
        # Validate shares outstanding is reasonable (positive and not too large)
        if shares is not None and shares > 0 and shares < 100000000000:  # Max 100 billion shares
            return shares
            
        return None


__all__ = ["MarketFactsEngine", "MarketFacts"]
