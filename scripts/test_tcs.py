import httpx
import asyncio

async def test():
    symbol = "TCS"
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.get(f'https://fundametrics-backend.onrender.com/api/company/{symbol}')
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Price: {r.json().get('live_market', {}).get('price', {}).get('value')}")

if __name__ == "__main__":
    asyncio.run(test())
