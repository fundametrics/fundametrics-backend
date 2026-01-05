from typing import Dict, Any, Optional
from scraper.core.fetcher import Fetcher
from scraper.sources.moneycontrol_parser import MoneycontrolParser
from scraper.utils.logger import logger

class MoneycontrolScraper:
    """
    Scraper for external company profile data.
    """
    
    BASE_URL = "https://www.external-source-2.com"
    SEARCH_URL = "https://www.external-source-2.com/stocks/csearch.php?str={symbol}"
    
    def __init__(self, fetcher: Optional[Fetcher] = None):
        self.fetcher = fetcher or Fetcher()

    async def scrape_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Scrapes company profile and basic metadata for a given symbol.
        """
        logger.info(f"Scraping external profile site for symbol: {symbol}")
        
        try:
            # 1. Resolve URL
            # Note: For many stocks, the search redirect works if headers are correct.
            target_url = await self._resolve_url(symbol)
            if not target_url:
                logger.error(f"Could not resolve profile URL for symbol: {symbol}")
                return {}
            
            logger.info(f"Resolved profile URL: {target_url}")
            
            # 2. Fetch HTML
            # External source often needs the same site as Referer
            html = await self.fetcher.fetch_html(target_url, referer=self.BASE_URL)
            if not html:
                logger.error(f"Failed to fetch profile page for {symbol}")
                return {}
            
            # 3. Parse HTML
            parser = MoneycontrolParser(html, symbol=symbol)
            data = parser.parse_all()
            
            if data:
                data["url"] = target_url
                logger.success(f"Successfully scraped profile source for {symbol}")
                
            return data
            
        except Exception as e:
            logger.exception(f"Unexpected error scraping external profile for {symbol}: {e}")
            return {}

    async def _resolve_url(self, symbol: str) -> Optional[str]:
        """
        Attempts to find the stock page URL on external source.
        """
        # Try direct search redirect
        url = self.SEARCH_URL.format(symbol=symbol)
        
        try:
            # We use httpx directly to check for redirects without downloading large HTML if possible, 
            # but our Fetcher handles it well too.
            # Using fetcher because it has rate limiting and retries.
            async with self.fetcher.client_manager() as client:
                response = await client.get(url, follow_redirects=True, timeout=15)
                
                # Check if we landed on a stock page
                # Stock pages usually have /stockpricequote/ in them
                if "/stockpricequote/" in str(response.url):
                    return str(response.url)
                
                # If we are still on csearch.php or home page, it failed to redirect directly
                logger.warning(f"Search redirect failed to find direct stock page for {symbol}. Landed on: {response.url}")
                
                # Debug: Log snippet of search page
                logger.debug(f"Search page snippet: {response.text[:1000]}")

                # Strategy 2: Try to find the first link in the search results if we landed on a search page
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'lxml')
                # Look for links containing stockpricequote
                # Often in a table with class 'mctable1' or similar
                links = soup.find_all('a', href=lambda h: h and "/stockpricequote/" in h)
                logger.debug(f"Found {len(links)} potential stock links on search page.")
                
                for link in links:
                    href = link['href']
                    # Look for exact symbol match in link text or href
                    if symbol.upper() in link.text.upper() or symbol.upper() in href.upper():
                        full_url = href
                        if not full_url.startswith("http"):
                            full_url = self.BASE_URL + full_url
                        return full_url
                        
                # Fallback: Just take the first stock link if any
                if links:
                    full_url = links[0]['href']
                    if not full_url.startswith("http"):
                        full_url = self.BASE_URL + full_url
                    return full_url

            return None
        except Exception as e:
            logger.error(f"Error resolving URL for {symbol}: {e}")
            return None
