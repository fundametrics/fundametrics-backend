"""
External Financial Data Scraper - High-level Scraper Class
===========================================================

Main scraper class for external financial data source that coordinates fetching and parsing.
"""

from typing import Dict, Any, Optional
from scraper.core.fetcher import Fetcher
from scraper.sources.screener_parser import ScreenerParser
from scraper.utils.logger import get_logger

log = get_logger(__name__)


class ScreenerScraper:
    """
    Scraper for external financial data source
    """
    
    def __init__(self, fetcher: Fetcher):
        """
        Initialize with a shared fetcher instance
        """
        self.fetcher = fetcher
        self.base_url = "https://www.screener.in"
        # Mapping for symbols that don't match Screener's expected URL pattern
        self._SYMBOL_MAP = {
            "TATAMOTORS": "TMCV",
            # Add other known discrepancies here
        }
        log.info("External financial data scraper initialized")

    async def scrape_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch and parse data for a single stock symbol
        
        Args:
            symbol: NSE/BSE symbol (e.g., RELIANCE)
            
        Returns:
            Structured dictionary of fundamental data
        """
        # Resolve to Screener slug if mapped
        slug = self._SYMBOL_MAP.get(symbol.upper(), symbol.upper())
        url = f"{self.base_url}/company/{slug}/"
        log.info(f"Scraping external financial data source for symbol: {symbol} (slug: {slug})")
        
        try:
            # Use the fetcher to get HTML (handles rate limiting and retries)
            html = await self.fetcher.fetch_html(url, referer=self.base_url)
            
            if not html:
                log.error(f"Failed to retrieve HTML for {symbol}")
                return {}
                
            # Parse the HTML
            parser = ScreenerParser(html, symbol=symbol)
            data = parser.parse_all()
            
            if not data:
                log.warning(f"No data parsed for {symbol}")
                return {}
                
            # Add metadata
            data["source"] = "external_source_1"
            data["url"] = url
            
            return data
            
        except Exception as e:
            log.exception(f"Unexpected error scraping {symbol} from external source: {e}")
            return {}

    async def get_search_results(self, query: str) -> Optional[str]:
        """
        Search for a stock symbol if the exact symbol is unknown (future implementation)
        """
        pass
