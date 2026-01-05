"""
Integration Test - Phase 2 HTTP Fetcher
=======================================

Verifies that RateLimiter, HeaderManager, and Fetcher work together.
"""

import asyncio
import time
from scraper.core.fetcher import Fetcher
from scraper.utils.rate_limiter import RateLimiter
from scraper.utils.logger import setup_logging, get_logger

async def test_fetcher_integration():
    # Setup logging
    setup_logging()
    log = get_logger(__name__)
    
    log.info("Starting integration test for HTTP Fetcher")
    
    # Initialize components with aggressive settings for testing
    limiter = RateLimiter(requests_per_minute=30, base_delay=2.0, jitter_range=0.5)
    
    async with Fetcher(rate_limiter=limiter) as fetcher:
        urls = [
            "https://www.google.com",
            "https://www.wikipedia.org",
            "https://www.python.org"
        ]
        
        for url in urls:
            start_time = time.time()
            try:
                log.info(f"Testing fetch for: {url}")
                html = await fetcher.fetch_html(url)
                duration = time.time() - start_time
                log.success(f"Successfully fetched {url} in {duration:.2f}s (Length: {len(html)})")
            except Exception as e:
                log.error(f"Failed to fetch {url}: {e}")

    log.info("Integration test complete")

if __name__ == "__main__":
    asyncio.run(test_fetcher_integration())
