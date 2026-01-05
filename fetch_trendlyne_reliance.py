import asyncio
import httpx

async def fetch_trendlyne_reliance():
    url = "https://trendlyne.com/equity/1127/RELIANCE/reliance-industries-ltd/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.get(url, headers=headers)
        if r.status_code == 200:
            with open("trendlyne_reliance_fixed.html", "w", encoding='utf-8') as f:
                f.write(r.text)
            print("Saved trendlyne_reliance_fixed.html")
        else:
            print(f"Failed to fetch: {r.status_code}")

if __name__ == "__main__":
    asyncio.run(fetch_trendlyne_reliance())
