import asyncio
import httpx

async def fetch_trendlyne_home():
    url = "https://trendlyne.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        if r.status_code == 200:
            with open("trendlyne_home.html", "w", encoding='utf-8') as f:
                f.write(r.text)
            print("Saved trendlyne_home.html")
        else:
            print(f"Failed to fetch home: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(fetch_trendlyne_home())
