"""
Headers Manager - Browser-like HTTP Headers
============================================

Manages browser-like HTTP headers for web scraping with:
- User-Agent rotation
- Intelligent header generation
- Referer management
- Cookie persistence (optional)
"""

import random
from typing import Dict, Optional, List
from scraper.utils.logger import get_logger

log = get_logger(__name__)

# Realistic browser User-Agents
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0"
}

class HeaderManager:
    """
    Manages and rotates HTTP headers to mimic real browsers
    """
    
    def __init__(self, user_agents: Optional[List[str]] = None):
        """
        Initialize HeaderManager
        
        Args:
            user_agents: Optional list of User-Agents to use
        """
        self.user_agents = user_agents or USER_AGENTS
        self.current_ua = random.choice(self.user_agents)
        log.debug("HeaderManager initialized")

    def get_headers(self, mode: str = "json", referer: Optional[str] = None, additional_headers: Optional[Dict] = None) -> Dict[str, str]:
        """
        Generate a fresh set of headers with context-aware fingerprinting.
        mode: 'json' for API calls, 'html' for page scraping
        """
        ua = random.choice(self.user_agents)
        
        headers = {
            "User-Agent": ua,
            "Accept-Language": random.choice([
                "en-US,en;q=0.9",
                "en-GB,en;q=0.8",
                "en-IN,en;q=0.9,hi;q=0.8"
            ]),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Site": "same-site" if "yahoo" in (referer or "") else "none",
        }

        if mode == "json":
            headers["Accept"] = "application/json, text/plain, */*"
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Dest"] = "empty"
        else:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-User"] = "?1"
            headers["Upgrade-Insecure-Requests"] = "1"

        if referer:
            headers["Referer"] = referer
            
        if additional_headers:
            headers.update(additional_headers)
            
        return headers

    def rotate_ua(self):
        """Explicitly rotate the current user agent"""
        self.current_ua = random.choice(self.user_agents)
        log.debug(f"Rotated User-Agent to: {self.current_ua[:50]}...")

    @classmethod
    def get_browser_headers(cls, url: str) -> Dict[str, str]:
        """Static method for quick header generation based on URL domain"""
        ua = random.choice(USER_AGENTS)
        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = ua
        
        # Add basic logic to set referer to domain root if possible
        try:
            from urllib.parse import urlparse
            domain = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
            headers["Referer"] = domain
        except Exception:
            pass
            
        return headers

if __name__ == "__main__":
    manager = HeaderManager()
    print("Sample Headers:")
    import json
    print(json.dumps(manager.get_headers(referer="https://www.google.com"), indent=2))
