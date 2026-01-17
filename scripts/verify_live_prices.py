import httpx
import asyncio
import json

async def check_company(symbol):
    url = f"https://fundametrics-backend.onrender.com/api/company/{symbol}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        try:
            response = await client.get(url)
            print(f"[{symbol}] Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                price = None
                for m in data.get("fundametrics_metrics", []):
                    if m["metric_name"] == "Current Price":
                        price = m["value"]
                        break
                print(f"[{symbol}] Price: {price}")
            else:
                print(f"[{symbol}] Error: {response.text}")
        except Exception as e:
            print(f"[{symbol}] Failed: {type(e).__name__} - {e}")

async def main():
    symbols = ["TCS", "INFY", "HINDUNILVR", "RELIANCE"]
    print("Verifying live prices...")
    for s in symbols:
        await check_company(s)

if __name__ == "__main__":
    asyncio.run(main())
