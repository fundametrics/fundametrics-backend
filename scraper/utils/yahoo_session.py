import asyncio
import httpx
from datetime import datetime
from typing import Optional, Dict
from scraper.utils.logger import get_logger
log = get_logger(__name__)

class YahooSession:
    """
    Manages Yahoo Finance sessions (Cookies + Crumbs) for reliable API access.
    Matches the pattern used by robust libraries to bypass 429/401 blocks.
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.cookies: Optional[Dict] = None
        self.crumb: Optional[str] = None
        self.last_update: Optional[datetime] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = YahooSession()
        return cls._instance

    async def refresh_if_needed(self):
        """Refresh session info if older than 1 hour or missing"""
        async with self._lock:
            now = datetime.now()
            if not self.crumb or not self.last_update or (now - self.last_update).total_seconds() > 3600:
                await self._refresh_session()

    async def _refresh_session(self):
        """Perform the Cookie/Crumb dance with Yahoo"""
        try:
            log.info("Refreshing Yahoo Finance session (Cookie + Crumb)...")
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0, follow_redirects=True) as client:
                # 1. Get initial cookie from the landing page
                response = await client.get("https://fc.yahoo.com/")
                self.cookies = dict(response.cookies)
                
                # 2. Get the crumb
                crumb_response = await client.get(
                    "https://query2.finance.yahoo.com/v1/test/getcrumb",
                    cookies=self.cookies
                )
                if crumb_response.status_code == 200:
                    self.crumb = crumb_response.text
                    self.last_update = datetime.now()
                    log.success("Yahoo session refreshed successfully. Crumb obtained.")
                else:
                    log.warning(f"Failed to get Yahoo crumb: {crumb_response.status_code}")
                    self.crumb = None 
                    
        except Exception as e:
            log.error(f"Error during Yahoo session refresh: {e}")
            self.crumb = None

    def get_api_params(self, base_params: Optional[Dict] = None) -> Dict:
        """Add session crumb to API parameters"""
        params = base_params or {}
        if self.crumb:
            params["crumb"] = self.crumb
        return params

    def get_cookies(self) -> Optional[Dict]:
        return self.cookies
