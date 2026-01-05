import asyncio
from scraper.core.fetcher import Fetcher

async def check():
    f = Fetcher()
    url = "https://www.screener.in/company/TATAMOTORS/"
    html = await f.fetch_html(url)
    with open("tata_debug.html", "w", encoding="utf-8") as f_out:
        f_out.write(html)
    print("Saved tata_debug.html")

if __name__ == "__main__":
    asyncio.run(check())
