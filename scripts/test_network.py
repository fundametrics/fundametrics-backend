import httpx
import asyncio

async def test():
    url = "https://www.google.com"
    print(f"Testing {url}...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
