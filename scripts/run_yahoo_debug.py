import httpx
import asyncio
import json

async def test():
    url = "https://fundametrics-backend.onrender.com/api/debug/yahoo/TCS"
    print(f"Testing debug endpoint: {url}")
    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            print(f"Response: {json.dumps(r.json(), indent=2)}")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
