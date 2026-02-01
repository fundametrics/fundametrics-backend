from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass

from scraper.core.fetcher import Fetcher
from scraper.utils.logger import get_logger


@dataclass(frozen=True)
class MarketFacts:
    """Immutable market facts data structure."""
    current_price: Optional[float]
    current_change: Optional[float]
    change_percent: Optional[float]
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
        
        # Phase 14: Early-Exit Ceasefire
        # Check lockdown status at the VERY START to avoid network slowness
        from scraper.utils.yahoo_session import YahooSession
        session = await YahooSession.get_instance()
        
        # NOTE: Reduced global locking strictness here to allow fallback attempts
        # only return empty if absolutely blocked (e.g. auth failure)
        # if session.is_in_quarantine(): ...
        
        # Optimized: Fetch ALL data in ONE request using fetch_batch_prices
        batch_results = await self.fetch_batch_prices([yahoo_symbol])
        data = batch_results[0] if batch_results else {}
        
        current_price = data.get("price")
        current_change = data.get("change")
        change_pct = data.get("change_percent") or data.get("changePercent")
        high_52w = data.get("fifty_two_week_high")
        low_52w = data.get("fifty_two_week_low")
        shares_outstanding = data.get("shares_outstanding")
        
        # Compute market cap internally
        market_cap = self._compute_market_cap(current_price, shares_outstanding)
        
        market_facts = MarketFacts(
            current_price=current_price,
            current_change=current_change,
            change_percent=change_pct,
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
                "change": market_facts.current_change,
                "change_percent": market_facts.change_percent,
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
        # Handle cases like "RELIANCE.NS" or "RELIANCE.BO"
        clean_symbol = symbol.split('.')[0] if '.' in symbol and not symbol.startswith('^') else symbol
        
        # Index symbols (starting with ^) should be used as-is.
        # Stocks usually need .NS or .BO suffix.
        suffixes = [""] if clean_symbol.startswith("^") else [".NS", ".BO"]
        for suffix in suffixes:
            try:
                import urllib.parse
                yahoo_symbol = f"{clean_symbol}{suffix}" if suffix else clean_symbol
                quoted_symbol = urllib.parse.quote(yahoo_symbol)
                url = f"https://query2.finance.yahoo.com/v8/finance/chart/{quoted_symbol}?interval=1d"
                
                # Use a specific short timeout for live market data
                response = await self._fetcher.fetch_json(url, timeout=5.0)
                
                if response and "chart" in response and response["chart"]["result"]:
                    result = response["chart"]["result"][0]
                    meta = result.get("meta", {})
                    
                    price = meta.get("regularMarketPrice")
                    if price is not None:
                        self._log.debug("Price found for {}: {}", yahoo_symbol, price)
                        return {
                            "current_price": float(price),
                            "change": meta.get("regularMarketChange"),
                            "change_percent": meta.get("regularMarketChangePercent"),
                            "delay_minutes": 15,
                            "currency": meta.get("currency", "INR"),
                            "timestamp": meta.get("regularMarketTime")
                        }
            except Exception as exc:
                sc = getattr(exc, 'status_code', None)
                # Fail-fast removed here too to allow fallback
                if sc == 429 or "429" in str(exc):
                    self._log.warning(f"Chart API 429 for {yahoo_symbol} - continuing to fallback")
                    continue
                self._log.warning("Yahoo fetch failed for {}{}: {}", clean_symbol, suffix, exc)
                continue
                
        return {}

    async def _scrape_index_html(self, index_symbol: str) -> Dict[str, Any]:
        """
        Phase 12: Human-Mimetic fallback. Scrapes public HTML if API is blocked.
        Harder to block as it doesn't require crumbs.
        """
        try:
            import urllib.parse
            import re
            from bs4 import BeautifulSoup
            
            quoted = urllib.parse.quote(index_symbol)
            url = f"https://finance.yahoo.com/quote/{quoted}"
            
            # Use 'clean' mode (no identity) for HTML to avoid cookie profiling
            html = await self._fetcher.fetch_html(url, timeout=10.0)
            if not html: return {}
            
            # 1. Primary: JSON blob extraction (most accurate)
            match = re.search(r'"regularMarketPrice":\s*\{"raw":\s*([\d\.]+)', html)
            if match:
                price = float(match.group(1))
                self._log.info(f"🍀 HTML Scrape Success (Regex): {index_symbol} = {price}")
                return {"current_price": price, "currency": "INR"}
                
            # 2. Fallback: BeautifulSoup parsing
            soup = BeautifulSoup(html, "html.parser")
            price_tag = soup.find("fin-streamer", {"data-field": "regularMarketPrice"})
            if price_tag and price_tag.get("value"):
                price = float(price_tag["value"])
                self._log.info(f"🍀 HTML Scrape Success (Soup): {index_symbol} = {price}")
                return {"current_price": price, "currency": "INR"}
                
        except Exception as e:
            self._log.debug(f"HTML Scrape failed for {index_symbol}: {e}")
            
        return {}

    async def _fetch_52_week_range(self, symbol: str) -> Dict[str, Any]:
        """Fetch 52-week high/low data from Yahoo Finance."""
        clean_symbol = symbol.split('.')[0] if '.' in symbol and not symbol.startswith('^') else symbol
        try:
            yahoo_symbol = f"{clean_symbol}.NS"
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d"
            response = await self._fetcher.fetch_json(url, timeout=5.0)
            
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
        except Exception:
            pass
        return {}

    async def _fetch_shares_outstanding(self, symbol: str) -> Dict[str, Any]:
        """Fetch shares outstanding data."""
        return {}

    async def fetch_batch_prices(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Production-Grade Fetcher (Phase 15):
        Hierarchy: Quote API (Batch) -> Chart API (Serial) -> HTML Scrape (Emergency)
        Prevents global lockdown on 429s by switching sources smartly.
        """
        if not symbols: return []
            
        from scraper.utils.yahoo_session import YahooSession
        session = await YahooSession.get_instance()
        await session.refresh_if_needed()
        
        results_map = {}
        
        # Chunk symbols to avoid URL length limits (max ~50 safe)
        chunks = [symbols[i:i + 50] for i in range(0, len(symbols), 50)]
        
        for chunk in chunks:
            chunk_success = False
            
            # --- STRATEGY 1: QUOTE API (BATCH - PRIMARY) ---
            try:
                # Try both subdomains if one fails
                for sub in ["query2", "query1"]:
                    if chunk_success: break
                    
                    symbols_str = ",".join(chunk)
                    url = f"https://{sub}.finance.yahoo.com/v7/finance/quote?symbols={symbols_str}"
                    
                    api_headers = session.get_headers({
                        "Accept": "application/json, text/plain, */*",
                        "Origin": "https://finance.yahoo.com",
                        "Referer": "https://finance.yahoo.com/"
                    })
                    
                    # Use session cookies/crumbs if available
                    params = session.get_api_params()
                    cookies = session.get_cookies()
                    
                    response = await self._fetcher.fetch_json(
                        url, timeout=10.0, headers=api_headers, params=params, cookies=cookies
                    )
                    
                    if response and "quoteResponse" in response and response["quoteResponse"].get("result"):
                        for r in response["quoteResponse"]["result"]:
                            sym = r.get("symbol")
                            if sym:
                                results_map[sym] = {
                                    "price": r.get("regularMarketPrice"),
                                    "change": r.get("regularMarketChange"),
                                    "change_percent": r.get("regularMarketChangePercent"),
                                    "fifty_two_week_high": r.get("fiftyTwoWeekHigh"),
                                    "fifty_two_week_low": r.get("fiftyTwoWeekLow"),
                                    "shares_outstanding": r.get("sharesOutstanding"),
                                    "market_cap": r.get("marketCap"),
                                    "symbol": sym,
                                    "currency": r.get("currency", "INR")
                                }
                        chunk_success = True
                        self._log.info(f"✅ Quote API Success ({sub}): Fetched {len(chunk)} symbols")
                        
            except Exception as e:
                self._log.warning(f"Quote API Batch failed: {e}")
            
            # --- STRATEGY 2: CHART API (SERIAL - SECONDARY) ---
            missing = [s for s in chunk if s not in results_map]
            
            if missing:
                self._log.debug(f"Falling back to Chart API for {len(missing)} symbols")
                for sym in missing:
                    try:
                        # Add slight delay to prevent burst flags
                        await asyncio.sleep(0.5)
                        
                        chart_data = await self._fetch_delayed_price(sym)
                        if chart_data and chart_data.get("current_price"):
                            results_map[sym] = {
                                "price": chart_data["current_price"],
                                "change": chart_data.get("change", 0), 
                                "change_percent": chart_data.get("change_percent", 0),
                                "symbol": sym, "currency": chart_data.get("currency", "INR")
                            }
                        else:
                            # --- STRATEGY 3: HTML SCRAPE (EMERGENCY - INDICES ONLY) ---
                            if sym.startswith('^'):
                                html_data = await self._scrape_index_html(sym)
                                if html_data:
                                    results_map[sym] = {
                                        "price": html_data["current_price"],
                                        "change": 0, "change_percent": 0,
                                        "symbol": sym, "currency": html_data.get("currency", "INR")
                                    }
                    except Exception as e:
                        # Individual symbol failure in fallback shouldn't stop the batch
                        self._log.warning(f"Chart API failed for {sym}: {e}")

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
