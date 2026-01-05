import json
from typing import Dict, Any, Optional
from scraper.core.fetcher import Fetcher
from scraper.sources.trendlyne_parser import TrendlyneParser
from scraper.utils.logger import get_logger

log = get_logger(__name__)

class TrendlyneScraper:
    """
    Scraper for external company profile data.
    """
    
    BASE_URL = "https://www.trendlyne.com"
    SEARCH_API = "https://www.trendlyne.com/member/api/ac_snames/stock/?term={symbol}"
    
    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    async def _resolve_url(self, symbol: str) -> Optional[str]:
        """
        Uses external source's autosuggest API to find the stock page URL.
        """
        url = self.SEARCH_API.format(symbol=symbol)
        
        try:
            # Merge default headers with custom ones
            headers = self.fetcher.header_manager.get_headers(referer=self.BASE_URL + "/")
            headers["X-Requested-With"] = "XMLHttpRequest"
            
            text = await self.fetcher.fetch_html(url, headers=headers)
            if text:
                data = json.loads(text)
                if data and isinstance(data, list):
                    # Find exact symbol match or first result
                    for item in data:
                        if item.get("id") == symbol.upper() or symbol.upper() in item.get("label", "").upper():
                            # Check if it has the nexturl or full link
                            next_url = item.get("nexturl")
                            if next_url:
                                if not next_url.startswith("http"):
                                    next_url = self.BASE_URL + next_url
                                return next_url
                            
                            # Fallback: check 'urls' list which sometimes contains [['Overview', 'url']]
                            urls = item.get("urls")
                            if urls and isinstance(urls, list) and len(urls) > 0:
                                u = urls[0][1]
                                if not u.startswith("http"):
                                    u = self.BASE_URL + u
                                return u
                
                log.warning(f"External profile search failed for {symbol}")
        except Exception as e:
            log.error(f"Error resolving external source URL for {symbol}: {e}")
        
        # Hardcoded fallbacks for manual discovery cases
        fallbacks = {
            "BHEL": "https://www.trendlyne.com/equity/189/BHEL/bharat-heavy-electricals-ltd/",
            "ONGC": "https://www.trendlyne.com/equity/1126/ONGC/oil-natural-gas-corporation-ltd/",
            "MRF": "https://www.trendlyne.com/equity/883/MRF/mrf-ltd/",
            "COALINDIA": "https://www.trendlyne.com/equity/353/COALINDIA/coal-india-ltd/"
        }
        if symbol.upper() in fallbacks:
            return fallbacks[symbol.upper()]
            
        return None

    async def scrape_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Main entry point to scrape a stock from external profile source.
        """
        log.info(f"Starting external profile scrape for {symbol}")
        
        # 1. Resolve URL
        stock_url = await self._resolve_url(symbol)
        if not stock_url:
            log.error(f"Could not resolve profile URL for {symbol}")
            return {}

        # 2. Fetch Main Page
        html_main = await self.fetcher.fetch_html(stock_url)
        if not html_main:
            log.error(f"Could not fetch profile main page for {symbol}")
            return {}

        parser = TrendlyneParser(html_main, symbol=symbol)
        data = parser.extract_sector_industry()
        about_url = parser.extract_about_url()
        
        # 3. Fetch About Page
        if about_url:
            log.info(f"Fetching profile About page: {about_url}")
            html_about = await self.fetcher.fetch_html(about_url)
            if html_about:
                about_parser = TrendlyneParser(html_about, symbol=symbol)
                about_data = about_parser.extract_profile_and_mgmt()
                data.update(about_data)
            else:
                log.warning(f"Could not fetch 'About' page for {symbol}")
        else:
            log.warning(f"Could not find 'About' URL for {symbol}")

        # Final Cleanup
        data["symbol"] = symbol
        data["source"] = "fundametrics.external.profile"
        data["url"] = stock_url
        
        return data
