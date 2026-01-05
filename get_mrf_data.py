import asyncio
import httpx
from bs4 import BeautifulSoup

async def get_mrf_data():
    url = "https://trendlyne.com/equity/883/MRF/mrf-ltd/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://trendlyne.com/"
    }
    
    print(f"Fetching data for MRF from {url}...")
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Extract and print clean text
                title = soup.title.string.strip() if soup.title else "No Title"
                print(f"\nPAGE TITLE: {title}\n")
                
                # Get all text
                text = soup.get_text(separator='\n', strip=True)
                
                # Save all text to a file
                with open('mrf_data.txt', 'w', encoding='utf-8') as f:
                    f.write(text)
                
                print("Successfully saved full text data to mrf_data.txt")
                print("--- PREVIEW (First 20 lines) ---")
                
                # Filter out too many empty lines
                lines = [line for line in text.split('\n') if line.strip()]
                for line in lines[:20]:
                    print(line)
                print("...\n(See mrf_data.txt for full output)")
                
            else:
                print(f"Failed to fetch page. Status code: {r.status_code}")
        except Exception as e:
            print(f"Error fetching data: {e}")

if __name__ == "__main__":
    asyncio.run(get_mrf_data())
