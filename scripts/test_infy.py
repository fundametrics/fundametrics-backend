import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get('https://fundametrics-backend.onrender.com/api/company/INFY')
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Price: {r.json().get('live_market', {}).get('price', {}).get('value')}")
            # print(f"Metrics: {[m['metric_name'] for m in r.json().get('fundametrics_metrics', [])]}")

if __name__ == "__main__":
    asyncio.run(test())
