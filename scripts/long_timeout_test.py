import httpx
import asyncio

async def test():
    symbol = "TCS"
    url = f"https://fundametrics-backend.onrender.com/api/company/{symbol}"
    print(f"Testing {symbol}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            r = await client.get(url)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                price = None
                for m in data.get("fundametrics_metrics", []):
                    if m["metric_name"] == "Current Price":
                        price = m["value"]
                        break
                print(f"Price: {price}")
            else:
                print(f"Error: {r.text}")
        except Exception as e:
            print(f"Failed: {type(e).__name__} - {e}")

if __name__ == "__main__":
    asyncio.run(test())
