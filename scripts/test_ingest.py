
import asyncio
import logging
import sys
import os

# Ensure root is in path
sys.path.append(os.getcwd())

from scraper.core.ingestion import ingest_symbol

# Configure logging to show everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def test():
    symbol = "TATAMOTORS"
    print(f"Testing ingestion for {symbol}...")
    try:
        result = await ingest_symbol(symbol)
        print("\nIngestion Result:")
        print(f"Status: {result.get('status')}")
        
        # Check payload size
        payload = result.get('storage_payload', {}).get('fundametrics_response', {})
        metrics = payload.get('computed_metrics', [])
        print(f"Metrics: {len(metrics)}")
        
    except Exception as e:
        print(f"\n❌ Ingestion Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
