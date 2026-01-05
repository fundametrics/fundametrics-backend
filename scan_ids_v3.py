import httpx
import asyncio
from bs4 import BeautifulSoup
import time

async def check_id(id):
    url = f"https://trendlyne.com/equity/{id}/"
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=h)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else "No Title"
                print(f"ID {id}: {title}")
            else:
                print(f"ID {id}: {r.status_code}")
        except Exception as e:
            print(f"ID {id}: Error {e}")

async def main():
    for i in range(130, 145):
        await check_id(i)
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(main())
