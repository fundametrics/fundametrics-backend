import httpx
import asyncio
from bs4 import BeautifulSoup

async def check_id(id):
    url = f"https://trendlyne.com/equity/{id}/"
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(url, headers=h)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'lxml')
            title = soup.title.string if soup.title else "No Title"
            print(f"ID {id}: {title}")
        else:
            print(f"ID {id}: {r.status_code}")

async def main():
    tasks = [check_id(i) for i in range(175, 190)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
