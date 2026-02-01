
import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.core.db import init_db, get_companies_col
from scraper.core.market_facts_engine import MarketFactsEngine

async def seed_market_data():
    """
    Manually fetch and update market facts for key stocks
    to populate Top Gainers/Losers immediately.
    """
    await init_db()
    col = get_companies_col()
    
    engine = MarketFactsEngine()
    
    # List of popular stocks to update immediately
    symbols = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
        "SBIN", "BHARTIARTL", "ITC", "LICI", "HINDUNILVR",
        "ADANIENT", "ADANIPORTS", "TATASTEEL", "TITAN", "BAJFINANCE",
        "ASIANPAINT", "MARUTI", "SUNPHARMA", "HCLTECH", "NTPC"
    ]
    
    print(f"🚀 Seeding market data for {len(symbols)} companies (BATCH MODE)...")
    
    # Prepare symbols (Yahoo needs suffixes for Indian stocks)
    yahoo_symbols = [f"{s}.NS" for s in symbols]
    
    # Fetch all at once using the new Quote API Batcher
    results = await engine.fetch_batch_prices(yahoo_symbols)
    
    for data in results:
        raw_sym = data.get("symbol")
        current_price = data.get("price")
        
        if current_price:
            # Clean symbol for DB lookup (RELIANCE.NS -> RELIANCE)
            db_symbol = raw_sym.replace(".NS", "")
            
            # Update DB
            update_data = {
                "snapshot.currentPrice": current_price,
                "snapshot.change": data.get("change"),
                "snapshot.changePercent": data.get("change_percent"),
                "snapshot.marketCap": data.get("market_cap"),
                "snapshot.fiftyTwoWeekHigh": data.get("fifty_two_week_high"),
                "snapshot.fiftyTwoWeekLow": data.get("fifty_two_week_low"),
                "snapshot.lastUpdated": datetime.now(timezone.utc)
            }
            
            # Only update fields that are not None
            update_query = {k: v for k, v in update_data.items() if v is not None}
            
            await col.update_one(
                {"symbol": db_symbol},
                {"$set": update_query}
            )
            print(f"✅ Updated {db_symbol}: Price={current_price}, Change={data.get('change_percent')}%")
        else:
            print(f"⚠️ No data returned for a symbol in batch")
            
    print("Done!")

if __name__ == "__main__":
    asyncio.run(seed_market_data())
