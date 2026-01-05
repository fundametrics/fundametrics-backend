"""
Batch Ingestion Script for NSE Companies
Designed for PC with limited resources - ingests companies in small batches with delays
"""
import asyncio
import time
from datetime import datetime
from scraper.core.ingestion import ingest_symbol
from scraper.core.mongo_repository import MongoRepository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 5  # Process 5 companies at a time
DELAY_BETWEEN_BATCHES = 60  # 1 minute delay between batches
DELAY_BETWEEN_SYMBOLS = 10  # 10 seconds between each symbol

async def get_nse_symbols():
    """Get all NSE symbols that need ingestion"""
    repo = MongoRepository()
    
    # Get all companies from the companies collection
    companies = list(repo.get_companies_col().find(
        {"exchange": "NSE"},
        {"symbol": 1, "_id": 0}
    ))
    
    symbols = [c["symbol"] for c in companies]
    logger.info(f"Found {len(symbols)} NSE companies to process")
    return symbols

async def ingest_batch(symbols_batch, batch_num, total_batches):
    """Ingest a batch of symbols"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Batch {batch_num}/{total_batches}")
    logger.info(f"Symbols: {', '.join(symbols_batch)}")
    logger.info(f"{'='*60}\n")
    
    for idx, symbol in enumerate(symbols_batch, 1):
        try:
            logger.info(f"[{idx}/{len(symbols_batch)}] Ingesting {symbol}...")
            start_time = time.time()
            
            # Run ingestion
            result = await asyncio.to_thread(ingest_symbol, symbol)
            
            elapsed = time.time() - start_time
            logger.info(f"✓ {symbol} completed in {elapsed:.2f}s")
            
            # Delay between symbols to avoid overwhelming the system
            if idx < len(symbols_batch):
                logger.info(f"Waiting {DELAY_BETWEEN_SYMBOLS}s before next symbol...")
                await asyncio.sleep(DELAY_BETWEEN_SYMBOLS)
                
        except Exception as e:
            logger.error(f"✗ Failed to ingest {symbol}: {str(e)}")
            continue

async def main():
    """Main batch ingestion process"""
    start_time = datetime.now()
    logger.info(f"Starting NSE Batch Ingestion at {start_time}")
    
    # Get all symbols
    symbols = await get_nse_symbols()
    
    if not symbols:
        logger.warning("No symbols found to ingest!")
        return
    
    # Calculate batches
    total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
    
    logger.info(f"\nIngestion Plan:")
    logger.info(f"  Total Symbols: {len(symbols)}")
    logger.info(f"  Batch Size: {BATCH_SIZE}")
    logger.info(f"  Total Batches: {total_batches}")
    logger.info(f"  Estimated Time: ~{(total_batches * BATCH_SIZE * DELAY_BETWEEN_SYMBOLS + total_batches * DELAY_BETWEEN_BATCHES) / 3600:.1f} hours")
    logger.info(f"\nStarting in 5 seconds...\n")
    await asyncio.sleep(5)
    
    # Process in batches
    for batch_num in range(total_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, len(symbols))
        batch = symbols[start_idx:end_idx]
        
        await ingest_batch(batch, batch_num + 1, total_batches)
        
        # Delay between batches (except for the last one)
        if batch_num < total_batches - 1:
            logger.info(f"\n⏸ Batch complete. Cooling down for {DELAY_BETWEEN_BATCHES}s...\n")
            await asyncio.sleep(DELAY_BETWEEN_BATCHES)
    
    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"Batch Ingestion Complete!")
    logger.info(f"Started: {start_time}")
    logger.info(f"Ended: {end_time}")
    logger.info(f"Duration: {duration}")
    logger.info(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
