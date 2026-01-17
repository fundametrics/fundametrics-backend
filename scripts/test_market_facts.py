import httpx
import asyncio

async def test():
    symbol = "TCS"
    url = f"https://fundametrics-backend.onrender.com/api/stocks/{symbol}/market"
    print(f"Testing {symbol} market facts...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                print(f"Data: {r.json().get('market', {}).get('price')}")
            else:
                print(f"Error: {r.text}")
        except Exception as e:
            print(f"Failed: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(test())
