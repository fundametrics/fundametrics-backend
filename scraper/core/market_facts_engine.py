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
        Fetch market facts for a given symbol.
        
        Args:
            symbol: Stock symbol (e.g., "BHEL", "RELIANCE")
            
        Returns:
            MarketFacts: Immutable market facts data structure
        """
        self._log.info("Fetching market facts for {}", symbol)
        
        # Fetch all market data concurrently
        price_data, range_data, shares_data = await asyncio.gather(
            self._fetch_delayed_price(symbol),
            self._fetch_52_week_range(symbol),
            self._fetch_shares_outstanding(symbol),
            return_exceptions=True
        )
        
        # Extract values with error handling
        current_price = self._extract_float(price_data, "current_price")
        price_delay = self._extract_int(price_data, "delay_minutes", default=20)
        high_52w = self._extract_float(range_data, "fifty_two_week_high")
        low_52w = self._extract_float(range_data, "fifty_two_week_low")
        shares_outstanding = self._extract_shares(shares_data)
        
        # Compute market cap internally
        market_cap = self._compute_market_cap(current_price, shares_outstanding)
        
        market_facts = MarketFacts(
            current_price=current_price,
            price_currency="INR",
            price_delay_minutes=price_delay,
            fifty_two_week_high=high_52w,
            fifty_two_week_low=low_52w,
            shares_outstanding=shares_outstanding,
            market_cap=market_cap,
            market_cap_currency="INR",
            last_updated=datetime.now(timezone.utc)
        )
        
        self._log.info(
            "Market facts retrieved for {}: price={}, delay={} min, market_cap={}",
            symbol, current_price, price_delay, market_cap
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
        """Fetch delayed price data from public source."""
        try:
            # Implementation would fetch from NSE/BSE public APIs or financial data providers
            # For now, return mock structure that would be populated by actual fetch
            url = f"https://api.example.com/market/price/{symbol}"
            response = await self._fetcher.get(url)
            
            if response:
                return {
                    "current_price": response.get("price"),
                    "delay_minutes": response.get("delay", 20),
                    "currency": "INR",
                    "timestamp": response.get("timestamp")
                }
                
        except Exception as exc:
            self._log.debug("Failed to fetch delayed price for {}: {}", symbol, exc)
            
        return {}

    async def _fetch_52_week_range(self, symbol: str) -> Dict[str, Any]:
        """Fetch 52-week high/low data from public source."""
        try:
            # Implementation would fetch from exchange APIs or financial data providers
            url = f"https://api.example.com/market/range/{symbol}"
            response = await self._fetcher.get(url)
            
            if response:
                return {
                    "fifty_two_week_high": response.get("high_52w"),
                    "fifty_two_week_low": response.get("low_52w"),
                    "currency": "INR"
                }
                
        except Exception as exc:
            self._log.debug("Failed to fetch 52-week range for {}: {}", symbol, exc)
            
        return {}

    async def _fetch_shares_outstanding(self, symbol: str) -> Dict[str, Any]:
        """Fetch shares outstanding data from public source."""
        try:
            # Implementation would fetch from company filings or financial data providers
            url = f"https://api.example.com/company/shares/{symbol}"
            response = await self._fetcher.get(url)
            
            if response:
                return {
                    "shares_outstanding": response.get("total_shares"),
                    "share_class": "equity",
                    "as_of_date": response.get("date")
                }
                
        except Exception as exc:
            self._log.debug("Failed to fetch shares outstanding for {}: {}", symbol, exc)
            
        return {}

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
