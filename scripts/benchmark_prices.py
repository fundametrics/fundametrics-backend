import httpx
import asyncio
import json

async def test():
    async with httpx.AsyncClient(timeout=45.0) as client:
        for symbol in ["INFY", "TCS"]:
            print(f"Testing {symbol}...")
            start = asyncio.get_event_loop().time()
            r = await client.get(f'https://fundametrics-backend.onrender.com/api/company/{symbol}')
            elapsed = asyncio.get_event_loop().time() - start
            print(f"[{symbol}] Status: {r.status_code}, Time: {elapsed:.2f}s")
            if r.status_code == 200:
                data = r.json()
                price = None
                for m in data.get("fundametrics_metrics", []):
                    if m["metric_name"] == "Current Price":
                        price = m["value"]
                        break
                print(f"[{symbol}] Price: {price}")
                print(f"[{symbol}] Live Market Price: {data.get('live_market', {}).get('price', {}).get('value')}")

if __name__ == "__main__":
    asyncio.run(test())
