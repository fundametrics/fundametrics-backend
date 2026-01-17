"""
HTTP Fetcher - Anti-Bot Safe Request Module
============================================

Production-grade HTTP client for web scraping with:
- Async requests via httpx
- Rate limiting (Token Bucket)
- User-Agent rotation
- Exponential backoff retries
- Proxy support
- Timeout management
- Controlled exception handling
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, Union, List
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from scraper.utils.logger import get_logger
from scraper.utils.headers import HeaderManager
from scraper.utils.rate_limiter import RateLimiter

log = get_logger(__name__)

# Custom Exceptions
class FetcherException(Exception):
    """Base exception for fetcher errors"""
    pass

class RateLimitException(FetcherException):
    """Raised when server returns 429 Too Many Requests"""
    pass

class PersistentError(FetcherException):
    """Raised when an error persists after retries"""
    pass

class BlockedException(FetcherException):
    """Raised when server returns 403 Forbidden or similar block"""
    pass

class Fetcher:
    """
    Robust HTTP client designed for reliable scraping
    """
    
    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        header_manager: Optional[HeaderManager] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        proxies: Optional[List[str]] = None
    ):
        """
        Initialize Fetcher with proxy rotation support
        """
        self.rate_limiter = rate_limiter or RateLimiter(requests_per_minute=10, base_delay=6.0, jitter_range=3.0)
        self.header_manager = header_manager or HeaderManager()
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxies = proxies or []
        self.current_proxy_idx = 0
        
        # Shuffle proxies for random start
        if self.proxies:
            import random
            random.shuffle(self.proxies)

        self.client = self._create_client()
        log.info(f"Fetcher initialized with {len(self.proxies)} proxies, timeout={timeout}s, max_retries={max_retries}")

    def _create_client(self) -> httpx.AsyncClient:
        """Create a new httpx client with the current proxy"""
        client_kwargs = {
            "timeout": httpx.Timeout(self.timeout),
            "follow_redirects": True,
        }
        
        if self.proxies:
            proxy = self.proxies[self.current_proxy_idx]
            client_kwargs["proxy"] = proxy
            log.debug(f"Creating client with proxy: {proxy}")
            
        return httpx.AsyncClient(**client_kwargs)

    def _rotate_proxy(self):
        """Rotates to the next proxy in the list"""
        if not self.proxies:
            return
            
        self.current_proxy_idx = (self.current_proxy_idx + 1) % len(self.proxies)
        proxy = self.proxies[self.current_proxy_idx]
        log.info(f"Rotating to proxy: {proxy}")
        
        # We need to recreate the client because httpx doesn't support changing proxies on the fly easily
        # Actually, we'll do this carefully.
        # Note: In a high-concurrency environment, this might be tricky, but for serial/low-concurrency it's fine.
        return self._create_client()

    async def close(self):
        """Close the underlying HTTP client"""
        await self.client.aclose()
        log.info("Fetcher client closed")

    @retry(
        stop=stop_after_attempt(5), # Initial + 4 retries = 5 total attempts
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type((httpx.RequestError, RateLimitException)),
        before_sleep=before_sleep_log(log, "WARNING"),
        reraise=True
    )
    async def _do_fetch(self, url: str, method: str = "GET", **kwargs) -> httpx.Response:
        """Internal method with retry logic and proxy rotation"""
        
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        referer = kwargs.pop("referer", None)
        if "headers" not in kwargs:
            kwargs["headers"] = self.header_manager.get_headers(referer=referer)
            
        try:
            log.debug(f"Fetching {method} {url}")
            response = await self.client.request(method, url, **kwargs)
            
            if response.status_code == 429:
                log.warning(f"Rate limited (429) for {url}")
                if hasattr(self.rate_limiter, 'on_rate_limit_error'):
                    self.rate_limiter.on_rate_limit_error()
                raise RateLimitException(f"Server returned 429 for {url}")
                
            if response.status_code == 200:
                if hasattr(self.rate_limiter, 'on_success'):
                    self.rate_limiter.on_success()
                return response
                
            if response.status_code == 403:
                log.error(f"Access forbidden (403) for {url}")
                if self.proxies:
                    log.info("Attempting proxy rotation due to 403 block")
                    # Close old client and create new one
                    old_client = self.client
                    self.client = self._rotate_proxy()
                    await old_client.aclose()
                raise BlockedException(f"Server returned 403 for {url}")
                
            log.error(f"Received unexpected status code {response.status_code} for {url}")
            response.raise_for_status()
            return response

        except (httpx.RequestError, BlockedException) as e:
            if isinstance(e, httpx.RequestError):
                log.error(f"Request Error: {type(e).__name__} for {url}")
            raise e 

    async def fetch_html(self, url: str, method: str = "GET", **kwargs) -> str:
        """
        Fetch HTML content from a URL safely
        
        Args:
            url: Target URL
            method: HTTP method (default: GET)
            **kwargs: Additional kwargs for httpx request
            
        Returns:
            HTML string
        """
        try:
            response = await self._do_fetch(url, method, **kwargs)
            return response.text
        except (RateLimitException, httpx.RequestError) as e:
            log.critical(f"Failed to fetch {url} after retries: {e}")
            raise PersistentError(f"Persistent failure for {url}") from e
        except BlockedException as e:
            raise e
        except Exception as e:
            log.exception(f"Unexpected error fetching {url}: {e}")
            raise FetcherException(f"Unexpected error: {str(e)}") from e

    async def fetch_json(self, url: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """
        Fetch JSON content from a URL safely
        
        Args:
            url: Target URL
            method: HTTP method (default: GET)
            **kwargs: Additional kwargs for httpx request
            
        Returns:
            Dict containing parsed JSON
        """
        try:
            response = await self._do_fetch(url, method, **kwargs)
            return response.json()
        except (RateLimitException, httpx.RequestError) as e:
            log.critical(f"Failed to fetch {url} after retries: {e}")
            raise PersistentError(f"Persistent failure for {url}") from e
        except Exception as e:
            log.exception(f"Unexpected error fetching {url}: {e}")
            return {} # Return empty dict on JSON decode error or other unexpected errors

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Alias for fetch_json for compatibility with MarketFactsEngine"""
        return await self.fetch_json(url, method="GET", **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

if __name__ == "__main__":
    # Simple test
    async def test():
        async with Fetcher() as f:
            try:
                html = await f.fetch_html("https://www.google.com")
                print(f"Succeesfully fetched {len(html)} bytes")
            except Exception as e:
                print(f"Failed: {e}")
                
    asyncio.run(test())
