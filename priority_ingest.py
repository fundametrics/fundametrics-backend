"""
Priority-based ingestion: Ingest high-value companies first
Focuses on Nifty 50, Nifty Next 50, and high market cap companies
"""
import asyncio
from scraper.core.ingestion import ingest_symbol
from scraper.core.mongo_repository import MongoRepository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Priority lists
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", 
    "SBIN", "BHARTIARTL", "BAJFINANCE", "KOTAKBANK", "LT", "ASIANPAINT", 
    "AXISBANK", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND",
    "WIPRO", "HCLTECH", "BAJAJFINSV", "ONGC", "NTPC", "POWERGRID", "TATAMOTORS",
    "TATASTEEL", "M&M", "ADANIPORTS", "COALINDIA", "JSWSTEEL", "INDUSINDBK",
    "GRASIM", "TECHM", "HINDALCO", "BRITANNIA", "DIVISLAB", "DRREDDY", "CIPLA",
    "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "SHREECEM", "UPL", "APOLLOHOSP",
    "TATACONSUM", "SBILIFE", "HDFCLIFE", "ADANIENT", "BPCL"
]

NIFTY_NEXT_50 = [
    "ADANIGREEN", "ADANIPOWER", "ADANITRANS", "AMBUJACEM", "ATGL", "AUROPHARMA",
    "BANDHANBNK", "BERGEPAINT", "BEL", "BOSCHLTD", "CHOLAFIN", "COLPAL",
    "DABUR", "DLF", "GAIL", "GODREJCP", "HAVELLS", "HDFCAMC", "ICICIPRULI",
    "INDIGO", "INDUSTOWER", "IOC", "JINDALSTEL", "LICHSGFIN", "LUPIN",
    "MARICO", "MCDOWELL-N", "MUTHOOTFIN", "NMDC", "NYKAA", "PAGEIND",
    "PETRONET", "PIDILITIND", "PNB", "RECLTD", "SAIL", "SIEMENS", "SRF",
    "TATAPOWER", "TORNTPHARM", "TRENT", "TVSMOTOR", "VEDL", "VOLTAS",
    "ZOMATO", "ZYDUSLIFE", "MOTHERSON", "CANBK", "ICICIGI", "BAJAJHLDNG"
]

async def priority_ingest():
    """Ingest companies in priority order"""
    logger.info("Starting Priority-Based Ingestion")
    logger.info("="*60)
    
    # Phase 1: Nifty 50
    logger.info("\n📊 Phase 1: Nifty 50 Companies")
    logger.info(f"Processing {len(NIFTY_50)} companies...")
    for idx, symbol in enumerate(NIFTY_50, 1):
        try:
            logger.info(f"[{idx}/{len(NIFTY_50)}] Ingesting {symbol}...")
            await asyncio.to_thread(ingest_symbol, symbol)
            logger.info(f"✓ {symbol} complete")
            await asyncio.sleep(5)  # Short delay
        except Exception as e:
            logger.error(f"✗ {symbol} failed: {e}")
    
    logger.info("\n✓ Nifty 50 Complete!\n")
    await asyncio.sleep(30)  # Longer break
    
    # Phase 2: Nifty Next 50
    logger.info("\n📊 Phase 2: Nifty Next 50 Companies")
    logger.info(f"Processing {len(NIFTY_NEXT_50)} companies...")
    for idx, symbol in enumerate(NIFTY_NEXT_50, 1):
        try:
            logger.info(f"[{idx}/{len(NIFTY_NEXT_50)}] Ingesting {symbol}...")
            await asyncio.to_thread(ingest_symbol, symbol)
            logger.info(f"✓ {symbol} complete")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"✗ {symbol} failed: {e}")
    
    logger.info("\n✓ Nifty Next 50 Complete!")
    logger.info("\n🎉 Priority ingestion finished! Top 100 companies are now available.")
    logger.info("Run batch_ingest_nse.py to process remaining companies in the background.")

if __name__ == "__main__":
    asyncio.run(priority_ingest())
