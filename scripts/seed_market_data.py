
import asyncio
import os
import sys

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
    
    print(f"🚀 Seeding market data for {len(symbols)} companies...")
    
    for symbol in symbols:
        try:
            print(f"Fetching {symbol}...")
            facts = await engine.fetch_market_facts(symbol)
            
            if facts.current_price:
                # Update DB
                update_data = {
                    "snapshot.currentPrice": facts.current_price,
                    "snapshot.change": facts.current_change,
                    "snapshot.changePercent": facts.change_percent,
                    "snapshot.marketCap": facts.market_cap,
                    "snapshot.pe": None, # Keep existing or calculate if creating fresh
                    "snapshot.roe": None
                }
                
                # Only update fields that are not None
                update_query = {k: v for k, v in update_data.items() if v is not None}
                
                await col.update_one(
                    {"symbol": symbol},
                    {"$set": update_query}
                )
                print(f"✅ Updated {symbol}: Price={facts.current_price}, Change={facts.change_percent}%")
            else:
                print(f"⚠️ No data for {symbol}")
                
        except Exception as e:
            print(f"❌ Error {symbol}: {e}")
            
    print("Done!")

if __name__ == "__main__":
    asyncio.run(seed_market_data())
