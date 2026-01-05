# Phase 22 — MongoDB Integration & Full Data Engine

**Status:** 🚀 In Progress  
**Start Date:** January 1, 2026  
**Target Completion:** January 8, 2026 (1 week)  
**Goal:** Transform Fundametrics into a production-grade platform with unlimited company support

---

## 🎯 Objectives

1. **Replace SQLite with MongoDB Atlas** (Free Tier - 512MB)
2. **Enable unlimited company ingestion** (not limited to 8 companies)
3. **Make all companies searchable** (like Screener.in)
4. **Production-ready backend** (scalable, cloud-hosted)
5. **Remove mock data dependency** (real data only)

---

## 📊 Current State vs Target State

| Feature | Current (Phase 21) | Target (Phase 22) |
|---------|-------------------|-------------------|
| Database | SQLite (local file) | MongoDB Atlas (cloud) |
| Companies | 8 (hardcoded) | Unlimited (scalable) |
| Search | Mock fallback | Real DB queries |
| Data Source | Manual ingestion | Automated scraper |
| Deployment | Local only | Cloud-ready |
| Scalability | Limited | Production-grade |

---

## 🏗️ Architecture Changes

### **Before (Phase 21)**
```
Frontend → API → SQLite (local) → JSON snapshots
                ↓
            Mock fallback (5 companies)
```

### **After (Phase 22)**
```
Frontend → API → MongoDB Atlas (cloud)
                ↓
            Real-time queries (unlimited companies)
```

---

## 📁 MongoDB Schema Design

### **Collection 1: `companies`**
```javascript
{
  "_id": "RELIANCE",  // Symbol as primary key
  "name": "Reliance Industries Limited",
  "sector": "Energy",
  "industry": "Refineries",
  "exchange": "NSE",
  "isin": "INE002A01018",
  "market_cap": 1900000,  // in Cr
  "website": "https://www.ril.com",
  "about": "India's largest private sector company...",
  "last_updated": ISODate("2026-01-01T00:00:00Z"),
  "data_quality": {
    "coverage_ratio": 92,
    "trust_grade": "A",
    "last_audit": ISODate("2026-01-01T00:00:00Z")
  }
}
```

**Indexes:**
- `_id` (symbol) - Primary key
- `sector` - For sector filtering
- `name` (text) - For search

---

### **Collection 2: `financials_annual`**
```javascript
{
  "_id": ObjectId("..."),
  "symbol": "RELIANCE",
  "year": "Mar 2024",
  "period_type": "annual",
  "statement_type": "income_statement",  // or balance_sheet, cash_flow
  "data": {
    "revenue": 739000,
    "expenses": 602000,
    "operating_profit": 137000,
    "net_profit": 92456,
    // ... all line items
  },
  "metadata": {
    "source": "screener.in",
    "scraped_at": ISODate("2026-01-01T00:00:00Z"),
    "run_id": "run-20260101-001"
  }
}
```

**Indexes:**
- `symbol` + `year` + `statement_type` (compound, unique)
- `symbol` (for company queries)

---

### **Collection 3: `financials_quarterly`**
```javascript
{
  "_id": ObjectId("..."),
  "symbol": "RELIANCE",
  "quarter": "Q2 FY25",
  "period_type": "quarterly",
  "statement_type": "income_statement",
  "data": {
    "revenue": 185000,
    "net_profit": 23000,
    // ... quarterly data
  },
  "metadata": {
    "source": "screener.in",
    "scraped_at": ISODate("2026-01-01T00:00:00Z")
  }
}
```

**Indexes:**
- `symbol` + `quarter` + `statement_type` (compound, unique)

---

### **Collection 4: `metrics`**
```javascript
{
  "_id": ObjectId("..."),
  "symbol": "RELIANCE",
  "period": "Mar 2024",
  "metric_name": "ROE",
  "value": 14.2,
  "unit": "%",
  "confidence": 0.95,
  "trust_score": {
    "grade": "A",
    "score": 95,
    "basis": "official_filings"
  },
  "drift": {
    "flag": "neutral",
    "z_score": 0.2,
    "magnitude": 0.5,
    "reason": "Within historical range"
  },
  "explainability": {
    "formula": "Net Profit / Average Shareholders Equity",
    "inputs": ["net_profit", "equity"],
    "assumptions": ["Consistent accounting policy"],
    "limitations": ["Does not account for off-balance sheet items"]
  },
  "source_provenance": {
    "calculation_agent": "Fundametrics Ratios Engine v2.4",
    "inputs_provenance": [
      {
        "metric": "Net Profit",
        "source": {
          "source": "Annual Report FY24",
          "statement_scope": "Consolidated"
        }
      }
    ]
  }
}
```

**Indexes:**
- `symbol` + `period` + `metric_name` (compound, unique)
- `symbol` (for company queries)
- `metric_name` (for cross-company comparisons)

---

### **Collection 5: `ownership`**
```javascript
{
  "_id": ObjectId("..."),
  "symbol": "RELIANCE",
  "quarter": "Q2 FY25",
  "summary": {
    "promoter": 49.11,
    "fii": 18.26,
    "dii": 13.42,
    "public": 19.21
  },
  "history": [
    {
      "quarter": "Q1 FY25",
      "promoter": 49.08,
      "fii": 18.10,
      "dii": 13.50,
      "public": 19.32
    }
  ],
  "insights": [
    {
      "title": "FII Accumulation",
      "description": "Foreign investors increased stake by 16 bps QoQ"
    }
  ]
}
```

**Indexes:**
- `symbol` + `quarter` (compound, unique)

---

### **Collection 6: `trust_metadata`**
```javascript
{
  "_id": ObjectId("..."),
  "symbol": "RELIANCE",
  "run_id": "run-20260101-001",
  "run_timestamp": ISODate("2026-01-01T00:00:00Z"),
  "coverage": {
    "score": 0.92,
    "coverage_ratio": 92,
    "available": ["company_profile", "financials_snapshot", "ratios"],
    "missing": []
  },
  "warnings": [
    {
      "code": "partial_data",
      "level": "info",
      "message": "Quarterly data not available for FY20"
    }
  ],
  "data_sources": {
    "screener": "https://www.screener.in/company/RELIANCE/",
    "bse_filings": "https://www.bseindia.com/..."
  }
}
```

**Indexes:**
- `symbol` (for company queries)
- `run_id` (for audit trail)

---

## 🔧 Implementation Steps

### **Phase 22.1: MongoDB Setup** (Day 1)

#### **Step 1: Create MongoDB Atlas Account**
1. Go to https://www.mongodb.com/cloud/atlas/register
2. Sign up with email
3. Create organization: "Fundametrics"
4. Create project: "Fundametrics Production"

#### **Step 2: Create Free Cluster**
1. Choose **M0 Free Tier**
2. Provider: **AWS**
3. Region: **Mumbai (ap-south-1)** (closest to India)
4. Cluster Name: **fundametrics-prod**
5. Storage: 512 MB (Free)

#### **Step 3: Configure Security**
1. **Database Access:**
   - Username: `fundametrics_api`
   - Password: (auto-generate strong password)
   - Role: `readWrite` on `fundametrics` database

2. **Network Access:**
   - Add IP: `0.0.0.0/0` (allow from anywhere)
   - Or specific IPs for production

#### **Step 4: Get Connection String**
```
mongodb+srv://fundametrics_api:<password>@fundametrics-prod.xxxxx.mongodb.net/fundametrics?retryWrites=true&w=majority
```

---

### **Phase 22.2: Backend Migration** (Day 2-3)

#### **Step 1: Install Dependencies**
```bash
cd fundametrics-scraper
pip install motor pymongo python-dotenv
pip freeze > requirements.txt
```

#### **Step 2: Create MongoDB Client**

**File:** `scraper/core/db.py` (NEW)
```python
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, TEXT
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
db = client["fundametrics"]

# Collections
companies_col = db["companies"]
financials_annual_col = db["financials_annual"]
financials_quarterly_col = db["financials_quarterly"]
metrics_col = db["metrics"]
ownership_col = db["ownership"]
trust_metadata_col = db["trust_metadata"]

async def init_indexes():
    """Create indexes for optimal query performance"""
    # Companies
    await companies_col.create_index("sector")
    await companies_col.create_index([("name", TEXT)])
    
    # Financials Annual
    await financials_annual_col.create_index(
        [("symbol", ASCENDING), ("year", ASCENDING), ("statement_type", ASCENDING)],
        unique=True
    )
    
    # Metrics
    await metrics_col.create_index(
        [("symbol", ASCENDING), ("period", ASCENDING), ("metric_name", ASCENDING)],
        unique=True
    )
    
    # Ownership
    await ownership_col.create_index(
        [("symbol", ASCENDING), ("quarter", ASCENDING)],
        unique=True
    )
    
    print("✅ MongoDB indexes created")

async def close_db():
    """Close MongoDB connection"""
    client.close()
```

#### **Step 3: Create MongoDB Repository**

**File:** `scraper/core/mongo_repository.py` (NEW)
```python
from typing import List, Dict, Optional
from scraper.core.db import (
    companies_col,
    financials_annual_col,
    metrics_col,
    ownership_col,
    trust_metadata_col
)

class MongoRepository:
    """MongoDB data access layer"""
    
    async def get_all_symbols(self) -> List[str]:
        """Get all company symbols"""
        cursor = companies_col.find({}, {"_id": 1})
        symbols = [doc["_id"] async for doc in cursor]
        return sorted(symbols)
    
    async def get_company(self, symbol: str) -> Optional[Dict]:
        """Get company profile"""
        return await companies_col.find_one({"_id": symbol})
    
    async def search_companies(self, query: str, limit: int = 25) -> List[Dict]:
        """Search companies by name or symbol"""
        results = []
        
        # Search by symbol (exact match)
        if query.isupper():
            doc = await companies_col.find_one({"_id": query})
            if doc:
                results.append(doc)
        
        # Search by name (text search)
        cursor = companies_col.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        async for doc in cursor:
            if doc not in results:
                results.append(doc)
        
        return results[:limit]
    
    async def get_financials(self, symbol: str, statement_type: str) -> List[Dict]:
        """Get financial statements for a symbol"""
        cursor = financials_annual_col.find(
            {"symbol": symbol, "statement_type": statement_type}
        ).sort("year", -1)
        
        return [doc async for doc in cursor]
    
    async def get_metrics(self, symbol: str) -> List[Dict]:
        """Get all metrics for a symbol"""
        cursor = metrics_col.find({"symbol": symbol}).sort("period", -1)
        return [doc async for doc in cursor]
    
    async def upsert_company(self, symbol: str, data: Dict):
        """Insert or update company profile"""
        await companies_col.update_one(
            {"_id": symbol},
            {"$set": data},
            upsert=True
        )
    
    async def upsert_financials(self, symbol: str, year: str, statement_type: str, data: Dict):
        """Insert or update financial statement"""
        await financials_annual_col.update_one(
            {"symbol": symbol, "year": year, "statement_type": statement_type},
            {"$set": data},
            upsert=True
        )
    
    async def upsert_metric(self, symbol: str, period: str, metric_name: str, data: Dict):
        """Insert or update metric"""
        await metrics_col.update_one(
            {"symbol": symbol, "period": period, "metric_name": metric_name},
            {"$set": data},
            upsert=True
        )
```

---

### **Phase 22.3: Update API Routes** (Day 4)

**File:** `scraper/api/routes.py` (UPDATE)
```python
from scraper.core.mongo_repository import MongoRepository

mongo_repo = MongoRepository()

@router.get("/stocks")
async def list_stocks():
    """Get all company symbols"""
    symbols = await mongo_repo.get_all_symbols()
    return {
        "count": len(symbols),
        "symbols": symbols
    }

@router.get("/stocks/{symbol}")
async def get_stock(symbol: str):
    """Get company details"""
    company = await mongo_repo.get_company(symbol.upper())
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Fetch financials
    income_statements = await mongo_repo.get_financials(symbol, "income_statement")
    balance_sheets = await mongo_repo.get_financials(symbol, "balance_sheet")
    cash_flows = await mongo_repo.get_financials(symbol, "cash_flow")
    
    # Fetch metrics
    metrics = await mongo_repo.get_metrics(symbol)
    
    # Build response (existing reshape logic)
    return _build_company_response(company, income_statements, metrics)

@router.get("/search")
async def search_symbols(query: str = Query("")):
    """Search companies"""
    if not query:
        return {"query": "", "results": [], "disclaimer": "..."}
    
    results = await mongo_repo.search_companies(query.strip())
    
    return {
        "query": query,
        "results": [
            {
                "symbol": r["_id"],
                "name": r["name"],
                "sector": r.get("sector", "Not disclosed")
            }
            for r in results
        ],
        "disclaimer": "Search results are informational only."
    }
```

---

### **Phase 22.4: Update Scraper** (Day 5)

**File:** `scraper/core/ingestion.py` (UPDATE)
```python
from scraper.core.mongo_repository import MongoRepository

async def ingest_symbol(symbol: str):
    """Ingest company data into MongoDB"""
    repo = MongoRepository()
    
    # Scrape data (existing logic)
    raw_data = await scrape_company(symbol)
    
    # Save company profile
    await repo.upsert_company(symbol, {
        "name": raw_data["name"],
        "sector": raw_data["sector"],
        "industry": raw_data["industry"],
        "last_updated": datetime.now(timezone.utc)
    })
    
    # Save financials
    for year, statements in raw_data["financials"].items():
        await repo.upsert_financials(
            symbol, year, "income_statement", statements["income_statement"]
        )
        await repo.upsert_financials(
            symbol, year, "balance_sheet", statements["balance_sheet"]
        )
    
    # Compute and save metrics
    metrics = compute_metrics(raw_data)
    for metric in metrics:
        await repo.upsert_metric(
            symbol, metric["period"], metric["metric_name"], metric
        )
    
    return {"symbol": symbol, "status": "success"}
```

---

### **Phase 22.5: Environment Configuration** (Day 6)

**File:** `.env` (UPDATE)
```bash
# MongoDB
MONGO_URI=mongodb+srv://fundametrics_api:<password>@fundametrics-prod.xxxxx.mongodb.net/fundametrics?retryWrites=true&w=majority

# API Settings
INGEST_ENABLED=true
ADMIN_API_KEY=your-secret-key-here
```

---

### **Phase 22.6: Bulk Ingestion Script** (Day 7)

**File:** `scripts/bulk_ingest.py` (NEW)
```python
import asyncio
from scraper.core.ingestion import ingest_symbol

# Top 50 NSE companies
SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR",
    "ICICIBANK", "KOTAKBANK", "SBIN", "BHARTIARTL", "BAJFINANCE",
    "ITC", "ASIANPAINT", "LT", "AXISBANK", "MARUTI",
    "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND", "WIPRO",
    "HCLTECH", "TATAMOTORS", "TATASTEEL", "POWERGRID", "NTPC",
    "ONGC", "COALINDIA", "BAJAJFINSV", "M&M", "TECHM",
    "ADANIPORTS", "DIVISLAB", "GRASIM", "DRREDDY", "CIPLA",
    "EICHERMOT", "BRITANNIA", "JSWSTEEL", "HINDALCO", "INDUSINDBK",
    "SHREECEM", "APOLLOHOSP", "BPCL", "ADANIENT", "TATACONSUM",
    "HEROMOTOCO", "SBILIFE", "BAJAJ-AUTO", "HDFCLIFE", "PIDILITIND"
]

async def main():
    for symbol in SYMBOLS:
        try:
            print(f"Ingesting {symbol}...")
            await ingest_symbol(symbol)
            print(f"✅ {symbol} complete")
            await asyncio.sleep(5)  # Rate limiting
        except Exception as e:
            print(f"❌ {symbol} failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Companies in DB | 50+ |
| Search latency | <200ms |
| API response time | <500ms |
| Data freshness | <24 hours |
| Uptime | 99.9% |

---

## 🚀 Deployment Checklist

- [ ] MongoDB Atlas cluster created
- [ ] Indexes created
- [ ] Backend updated to use MongoDB
- [ ] API routes migrated
- [ ] Scraper updated
- [ ] Bulk ingestion complete (50+ companies)
- [ ] Frontend tested with real data
- [ ] Mock data disabled in production
- [ ] Environment variables configured
- [ ] Backend deployed to Railway/Render

---

## 📝 Next Steps After Phase 22

1. **Phase 22.7:** Remove mock data dependency
2. **Phase 22.8:** Add caching layer (Redis)
3. **Phase 22.9:** Implement real-time updates
4. **Phase 23:** Advanced analytics & peer comparison

---

**Status:** Ready to implement  
**Estimated Time:** 7 days  
**Risk Level:** Low (well-defined scope)
