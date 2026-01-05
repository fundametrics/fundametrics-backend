import asyncio
import sys
from scraper.core.ingestion import ingest_symbol
from scraper.core.storage import write_company_snapshot

async def main():
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["BHEL"]
    print(f"Starting ingestion override for: {symbols}")
    
    for symbol in symbols:
        try:
            print(f"Ingesting {symbol}...")
            result = await ingest_symbol(symbol)
            path = write_company_snapshot(result["symbol"], result["storage_payload"])
            print(f"Ingestion successful for {symbol}. Data stored at: {path}")
        except Exception as e:
            print(f"Failed to ingest {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
