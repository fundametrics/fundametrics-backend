import httpx
import asyncio

async def test_yahoo():
    symbol = "TCS.NS"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=10.0)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                print(f"Price for {symbol}: {price}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_yahoo())
