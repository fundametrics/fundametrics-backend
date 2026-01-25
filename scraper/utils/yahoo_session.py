import asyncio
import httpx
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from scraper.utils.logger import get_logger
log = get_logger(__name__)

# Sophisticated Browser Identity Mappings (UA -> Sec-Ch-Ua)
IDENTITY_POOL = [
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "hints": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"Windows"'
    },
    {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "hints": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"macOS"'
    },
    {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/131.0.0.0 Safari/537.36",
        "hints": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "platform": '"Windows"'
    },
    {
        "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "hints": '"Google Chrome";v="130", "Chromium";v="130", "Not_A Brand";v="24"',
        "platform": '"Linux"'
    }
]

class YahooSession:
    """
    Nuclear Stealth Yahoo Session Manager.
    Aligns UA with Client hints and maintains consistency to avoid bot flags.
    """
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self.cookies: Optional[Dict] = None
        self.crumb: Optional[str] = None
        self.last_update: Optional[datetime] = None
        self.quarantine_until: Optional[datetime] = None
        
        # Identity Consistency
        self.identity = random.choice(IDENTITY_POOL)
        self.req_count = 0
        self.max_req_per_id = 5 # Rotate identity every 5 calls
        
        self.base_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document"
        }

    @classmethod
    async def get_instance(cls):
        if not cls._instance:
            cls._instance = YahooSession()
        return cls._instance

    def is_in_quarantine(self) -> bool:
        if not self.quarantine_until:
            return False
        if datetime.now() > self.quarantine_until:
            self.quarantine_until = None 
            return False
        return True

    async def trigger_quarantine(self, minutes: int = 30):
        async with self._lock:
            self.quarantine_until = datetime.now() + timedelta(minutes=minutes)
            log.warning(f"⚠️ YAHOO NUCLEAR LOCKDOWN: Silent until {self.quarantine_until.strftime('%H:%M:%S')}")

    async def refresh_if_needed(self):
        if self.is_in_quarantine(): return
        async with self._lock:
            now = datetime.now()
            if not self.cookies or not self.last_update or (now - self.last_update).total_seconds() > 1800:
                await self._refresh_session()

    async def _refresh_session(self):
        try:
            self._rotate_identity()
            log.info("Refreshing Yahoo Identity (Stealth Mode)...")
            
            headers = self.get_headers()
            async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
                response = await client.get("https://finance.yahoo.com/")
                self.cookies = dict(response.cookies)
                
                crumb_response = await client.get(
                    "https://query2.finance.yahoo.com/v1/test/getcrumb",
                    cookies=self.cookies
                )
                if crumb_response.status_code == 200:
                    self.crumb = crumb_response.text.strip()
                    self.last_update = datetime.now()
                    log.success("Yahoo Stealth Identity Secured.")
                else:
                    self.crumb = None
                    self.last_update = datetime.now()
                    
        except Exception as e:
            log.error(f"Yahoo session failure: {e}")
            self.crumb = None

    def _rotate_identity(self):
        self.identity = random.choice(IDENTITY_POOL)
        self.req_count = 0

    def get_api_params(self, base_params: Optional[Dict] = None) -> Dict:
        params = base_params or {}
        if self.crumb: params["crumb"] = self.crumb
        return params

    def get_headers(self, additional: Optional[Dict] = None) -> Dict:
        """Alignment-Corrected Headers (Ghost-Mode Phase 11)"""
        self.req_count += 1
        if self.req_count > self.max_req_per_id:
            self._rotate_identity()

        h = self.base_headers.copy()
        h["User-Agent"] = self.identity["ua"]
        h["Sec-Ch-Ua"] = self.identity["hints"]
        h["Sec-Ch-Ua-Platform"] = self.identity["platform"]
        h["Sec-Ch-Ua-Mobile"] = "?0"
        
        if additional: h.update(additional)
        return h

    async def clear_crumb(self):
        async with self._lock:
            self.crumb = None
            self.cookies = None
            self.last_update = None
            self._rotate_identity()

    def get_cookies(self) -> Optional[Dict]:
        return self.cookies
