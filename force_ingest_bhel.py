import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scraper.core.ingestion import ingest_symbol
from scraper.core.storage import write_company_snapshot

async def force_ingest():
    symbol = "BHEL"
    print(f"--- FORCING INGESTION FOR: {symbol} ---")
    
    try:
        result = await ingest_symbol(symbol)
        print(f"Ingestion successful for {symbol}")
        print(f"Blocks ingested: {result['blocks_ingested']}")
        
        stored_at = write_company_snapshot(result["symbol"], result["storage_payload"])
        print(f"Data stored in repository at: {stored_at}")
        
    except Exception as e:
        print(f"Ingestion failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(force_ingest())
