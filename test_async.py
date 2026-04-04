import asyncio
from scraper.main import run_scraper
from dotenv import load_dotenv

load_dotenv()

async def test():
    print('Running thread')
    await asyncio.to_thread(run_scraper, symbol='RELIANCE', trendlyne=False, persist_runs=False)
    print('Thread done')

if __name__ == "__main__":
    asyncio.run(test())
