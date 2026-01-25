import asyncio
import httpx
import random
from datetime import datetime
from typing import Optional, Dict, List
from scraper.utils.logger import get_logger
log = get_logger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
]

class YahooSession:
    """
    Manages Yahoo Finance sessions (Cookies + Crumbs) for reliable API access.
    Ensures identical fingerprints across the session lifecycle.
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.cookies: Optional[Dict] = None
        self.crumb: Optional[str] = None
        self.last_update: Optional[datetime] = None
        self.quarantine_until: Optional[datetime] = None
        self.ua = random.choice(USER_AGENTS)
        
        self.base_headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = YahooSession()
        return cls._instance

    def is_in_quarantine(self) -> bool:
        """Check if we are currently backing off due to 429"""
        if not self.quarantine_until:
            return False
        if datetime.now() > self.quarantine_until:
            self.quarantine_until = None # Reset
            return False
        return True

    async def trigger_quarantine(self, minutes: int = 10):
        """Invoke lockout period when rate limited"""
        async with self._lock:
            self.quarantine_until = datetime.now() + timedelta(minutes=minutes)
            log.warning(f"⚠️ Yahoo Finance quarantined until {self.quarantine_until.strftime('%H:%M:%S')}")

    async def refresh_if_needed(self):
        """Refresh session info if older than 1 hour or missing"""
        if self.is_in_quarantine():
            return

        async with self._lock:
            now = datetime.now()
            # If crumb is missing but cookies exist, we might be okay. 
            # If both missing or too old, refresh.
            if not self.cookies or not self.last_update or (now - self.last_update).total_seconds() > 3600:
                await self._refresh_session()

    async def _refresh_session(self):
        """Perform the Cookie/Crumb dance with Yahoo"""
        try:
            # Rotate UA on refresh to avoid persistent IP/UA blocks
            self.ua = random.choice(USER_AGENTS)
            self.base_headers["User-Agent"] = self.ua
            
            log.info("Refreshing Yahoo Finance session...")
            async with httpx.AsyncClient(headers=self.base_headers, timeout=10.0, follow_redirects=True) as client:
                # 1. Get initial cookie from main Yahoo page
                response = await client.get("https://finance.yahoo.com/")
                self.cookies = dict(response.cookies)
                
                # 2. Get the crumb using the SAME cookies and UA
                # Note: We try query2 as it's the primary for crumbs
                crumb_response = await client.get(
                    "https://query2.finance.yahoo.com/v1/test/getcrumb",
                    cookies=self.cookies
                )
                if crumb_response.status_code == 200:
                    self.crumb = crumb_response.text.strip()
                    self.last_update = datetime.now()
                    log.success(f"Yahoo session active. Crumb secured.")
                else:
                    log.warning(f"Yahoo crumb failed ({crumb_response.status_code}). Proceeding with cookies only.")
                    self.crumb = None
                    self.last_update = datetime.now() # Still mark updated so we don't spam 429
                    
        except Exception as e:
            log.error(f"Yahoo session failure: {e}")
            self.crumb = None

    def get_api_params(self, base_params: Optional[Dict] = None) -> Dict:
        params = base_params or {}
        # Only add crumb if we actually have one. 
        # Adding crumb=None or empty string causes 401.
        if self.crumb:
            params["crumb"] = self.crumb
        return params

    def get_headers(self, additional: Optional[Dict] = None) -> Dict:
        h = self.base_headers.copy()
        if additional:
            h.update(additional)
        return h

    async def clear_crumb(self):
        """Clear current crumb and cookies to force a full refresh on next try"""
        async with self._lock:
            self.crumb = None
            self.cookies = None
            self.last_update = None
            log.info("Yahoo session cleared (Identity reset)")

    def get_cookies(self) -> Optional[Dict]:
        return self.cookies
