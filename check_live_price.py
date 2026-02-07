import asyncio
import logging
from scraper.core.market_facts_engine import MarketFactsEngine
from scraper.core.fetcher import Fetcher
from scraper.utils.rate_limiter import RateLimiter

async def main():
    logging.basicConfig(level=logging.INFO)
    fetcher = Fetcher(rate_limiter=RateLimiter(requests_per_minute=30, base_delay=2.0))
    engine = MarketFactsEngine(fetcher=fetcher)
    
    symbol = "RELIANCE"
    print(f"Fetching live data for {symbol}...")
    facts = await engine.fetch_market_facts(symbol)
    print(f"Live Price: {facts.current_price}")
    print(f"Market Cap: {facts.market_cap}")
    print(f"Change: {facts.current_change}%")

if __name__ == "__main__":
    asyncio.run(main())
