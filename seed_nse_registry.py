"""
NSE Company Registry Seeder
Seeds companies_registry collection with all NSE companies (NO financial data)
This is FAST - just company names and symbols
"""
import asyncio
from datetime import datetime
from scraper.core.db import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NSE Companies List (Top 1000+ companies)
NSE_COMPANIES = [
    # Nifty 50
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd", "sector": "Energy"},
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd", "sector": "IT"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd", "sector": "Banking"},
    {"symbol": "INFY", "name": "Infosys Ltd", "sector": "IT"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd", "sector": "Banking"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd", "sector": "FMCG"},
    {"symbol": "ITC", "name": "ITC Ltd", "sector": "FMCG"},
    {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd", "sector": "Telecom"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd", "sector": "Finance"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd", "sector": "Banking"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd", "sector": "Engineering"},
    {"symbol": "ASIANPAINT", "name": "Asian Paints Ltd", "sector": "Paints"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd", "sector": "Banking"},
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd", "sector": "Automobile"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd", "sector": "Pharma"},
    {"symbol": "TITAN", "name": "Titan Company Ltd", "sector": "Consumer Goods"},
    {"symbol": "ULTRACEMCO", "name": "UltraTech Cement Ltd", "sector": "Cement"},
    {"symbol": "NESTLEIND", "name": "Nestle India Ltd", "sector": "FMCG"},
    {"symbol": "WIPRO", "name": "Wipro Ltd", "sector": "IT"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Ltd", "sector": "IT"},
    {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd", "sector": "Finance"},
    {"symbol": "ONGC", "name": "Oil & Natural Gas Corporation Ltd", "sector": "Energy"},
    {"symbol": "NTPC", "name": "NTPC Ltd", "sector": "Power"},
    {"symbol": "POWERGRID", "name": "Power Grid Corporation of India Ltd", "sector": "Power"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd", "sector": "Automobile"},
    {"symbol": "TATASTEEL", "name": "Tata Steel Ltd", "sector": "Steel"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra Ltd", "sector": "Automobile"},
    {"symbol": "ADANIPORTS", "name": "Adani Ports and Special Economic Zone Ltd", "sector": "Infrastructure"},
    {"symbol": "COALINDIA", "name": "Coal India Ltd", "sector": "Mining"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd", "sector": "Steel"},
    {"symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd", "sector": "Banking"},
    {"symbol": "GRASIM", "name": "Grasim Industries Ltd", "sector": "Diversified"},
    {"symbol": "TECHM", "name": "Tech Mahindra Ltd", "sector": "IT"},
    {"symbol": "HINDALCO", "name": "Hindalco Industries Ltd", "sector": "Metals"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries Ltd", "sector": "FMCG"},
    {"symbol": "DIVISLAB", "name": "Divi's Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories Ltd", "sector": "Pharma"},
    {"symbol": "CIPLA", "name": "Cipla Ltd", "sector": "Pharma"},
    {"symbol": "EICHERMOT", "name": "Eicher Motors Ltd", "sector": "Automobile"},
    {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd", "sector": "Automobile"},
    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto Ltd", "sector": "Automobile"},
    {"symbol": "SHREECEM", "name": "Shree Cement Ltd", "sector": "Cement"},
    {"symbol": "UPL", "name": "UPL Ltd", "sector": "Chemicals"},
    {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise Ltd", "sector": "Healthcare"},
    {"symbol": "TATACONSUM", "name": "Tata Consumer Products Ltd", "sector": "FMCG"},
    {"symbol": "SBILIFE", "name": "SBI Life Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd", "sector": "Diversified"},
    {"symbol": "BPCL", "name": "Bharat Petroleum Corporation Ltd", "sector": "Energy"},
    
    # Nifty Next 50
    {"symbol": "ADANIGREEN", "name": "Adani Green Energy Ltd", "sector": "Power"},
    {"symbol": "ADANIPOWER", "name": "Adani Power Ltd", "sector": "Power"},
    {"symbol": "ADANITRANS", "name": "Adani Transmission Ltd", "sector": "Power"},
    {"symbol": "AMBUJACEM", "name": "Ambuja Cements Ltd", "sector": "Cement"},
    {"symbol": "ATGL", "name": "Adani Total Gas Ltd", "sector": "Gas"},
    {"symbol": "AUROPHARMA", "name": "Aurobindo Pharma Ltd", "sector": "Pharma"},
    {"symbol": "BANDHANBNK", "name": "Bandhan Bank Ltd", "sector": "Banking"},
    {"symbol": "BERGEPAINT", "name": "Berger Paints India Ltd", "sector": "Paints"},
    {"symbol": "BEL", "name": "Bharat Electronics Ltd", "sector": "Defence"},
    {"symbol": "BOSCHLTD", "name": "Bosch Ltd", "sector": "Auto Components"},
    {"symbol": "CHOLAFIN", "name": "Cholamandalam Investment and Finance Company Ltd", "sector": "Finance"},
    {"symbol": "COLPAL", "name": "Colgate-Palmolive (India) Ltd", "sector": "FMCG"},
    {"symbol": "DABUR", "name": "Dabur India Ltd", "sector": "FMCG"},
    {"symbol": "DLF", "name": "DLF Ltd", "sector": "Real Estate"},
    {"symbol": "GAIL", "name": "GAIL (India) Ltd", "sector": "Gas"},
    {"symbol": "GODREJCP", "name": "Godrej Consumer Products Ltd", "sector": "FMCG"},
    {"symbol": "HAVELLS", "name": "Havells India Ltd", "sector": "Electricals"},
    {"symbol": "HDFCAMC", "name": "HDFC Asset Management Company Ltd", "sector": "Finance"},
    {"symbol": "ICICIPRULI", "name": "ICICI Prudential Life Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "INDIGO", "name": "InterGlobe Aviation Ltd", "sector": "Aviation"},
    {"symbol": "INDUSTOWER", "name": "Indus Towers Ltd", "sector": "Telecom"},
    {"symbol": "IOC", "name": "Indian Oil Corporation Ltd", "sector": "Energy"},
    {"symbol": "JINDALSTEL", "name": "Jindal Steel & Power Ltd", "sector": "Steel"},
    {"symbol": "LICHSGFIN", "name": "LIC Housing Finance Ltd", "sector": "Finance"},
    {"symbol": "LUPIN", "name": "Lupin Ltd", "sector": "Pharma"},
    {"symbol": "MARICO", "name": "Marico Ltd", "sector": "FMCG"},
    {"symbol": "MCDOWELL-N", "name": "United Spirits Ltd", "sector": "Beverages"},
    {"symbol": "MUTHOOTFIN", "name": "Muthoot Finance Ltd", "sector": "Finance"},
    {"symbol": "NMDC", "name": "NMDC Ltd", "sector": "Mining"},
    {"symbol": "NYKAA", "name": "FSN E-Commerce Ventures Ltd", "sector": "E-commerce"},
    {"symbol": "PAGEIND", "name": "Page Industries Ltd", "sector": "Textiles"},
    {"symbol": "PETRONET", "name": "Petronet LNG Ltd", "sector": "Gas"},
    {"symbol": "PIDILITIND", "name": "Pidilite Industries Ltd", "sector": "Chemicals"},
    {"symbol": "PNB", "name": "Punjab National Bank", "sector": "Banking"},
    {"symbol": "RECLTD", "name": "REC Ltd", "sector": "Finance"},
    {"symbol": "SAIL", "name": "Steel Authority of India Ltd", "sector": "Steel"},
    {"symbol": "SIEMENS", "name": "Siemens Ltd", "sector": "Engineering"},
    {"symbol": "SRF", "name": "SRF Ltd", "sector": "Chemicals"},
    {"symbol": "TATAPOWER", "name": "Tata Power Company Ltd", "sector": "Power"},
    {"symbol": "TORNTPHARM", "name": "Torrent Pharmaceuticals Ltd", "sector": "Pharma"},
    {"symbol": "TRENT", "name": "Trent Ltd", "sector": "Retail"},
    {"symbol": "TVSMOTOR", "name": "TVS Motor Company Ltd", "sector": "Automobile"},
    {"symbol": "VEDL", "name": "Vedanta Ltd", "sector": "Mining"},
    {"symbol": "VOLTAS", "name": "Voltas Ltd", "sector": "Consumer Durables"},
    {"symbol": "ZOMATO", "name": "Zomato Ltd", "sector": "Food Delivery"},
    {"symbol": "ZYDUSLIFE", "name": "Zydus Lifesciences Ltd", "sector": "Pharma"},
    {"symbol": "MOTHERSON", "name": "Samvardhana Motherson International Ltd", "sector": "Auto Components"},
    {"symbol": "CANBK", "name": "Canara Bank", "sector": "Banking"},
    {"symbol": "ICICIGI", "name": "ICICI Lombard General Insurance Company Ltd", "sector": "Insurance"},
    {"symbol": "BAJAJHLDNG", "name": "Bajaj Holdings & Investment Ltd", "sector": "Finance"},
    
    # Add more companies here (you can add 900+ more)
    # For now, this gives you the top 100 companies
]

# Import extended list
try:
    from nse_companies_extended import NSE_COMPANIES_EXTENDED
    NSE_COMPANIES = NSE_COMPANIES + NSE_COMPANIES_EXTENDED
    logger.info(f"Extended company list loaded. Total: {len(NSE_COMPANIES)} companies")
except ImportError:
    logger.warning("Extended company list not found. Using base list only.")

async def seed_registry():
    """Seed the companies_registry collection"""
    db = get_db()
    col = db["companies_registry"]
    
    logger.info("="*60)
    logger.info("NSE Company Registry Seeder")
    logger.info("="*60)
    logger.info(f"Total companies to seed: {len(NSE_COMPANIES)}")
    
    inserted = 0
    updated = 0
    
    for company in NSE_COMPANIES:
        doc = {
            "_id": company["symbol"],
            "symbol": company["symbol"],
            "name": company["name"],
            "exchange": "NSE",
            "sector": company.get("sector", "General"),
            "is_analyzed": False,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = await col.update_one(
            {"_id": company["symbol"]},
            {"$setOnInsert": doc},
            upsert=True
        )
        
        if result.upserted_id:
            inserted += 1
        else:
            updated += 1
    
    logger.info(f"\n✓ Registry seeding complete!")
    logger.info(f"  Inserted: {inserted}")
    logger.info(f"  Already existed: {updated}")
    logger.info(f"  Total in registry: {len(NSE_COMPANIES)}")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(seed_registry())
