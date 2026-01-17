import httpx
import asyncio
import json

async def check_health():
    url = "https://fundametrics-backend.onrender.com/api/health"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=15.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {json.dumps(response.json(), indent=2)}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(check_health())
