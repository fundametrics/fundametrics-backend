# Two-Layer Company System - Implementation Guide

## 🎯 **What We Built**

A **smart two-layer system** that solves the PC problem:

### **Layer 1: Registry (Fast)**
- `companies_registry` collection
- Just company names + symbols
- **No financial data**
- Seeds in <10 seconds

### **Layer 2: Full Data (On-Demand)**
- `companies` collection  
- Complete financial ingestion
- Only runs when user clicks "Analyze"
- **Your PC stays cool** ✨

---

## 📋 **Setup Steps (5 Minutes)**

### **Step 1: Seed the Registry**
```bash
cd "c:/Users/Laser cote/.gemini/antigravity/scratch/finox-scraper"
py seed_nse_registry.py
```

**Expected Output:**
```
=============================================================
NSE Company Registry Seeder
=============================================================
Total companies to seed: 100

✓ Registry seeding complete!
  Inserted: 100
  Already existed: 0
  Total in registry: 100
=============================================================
```

**Time**: ~5 seconds
**PC Impact**: None

---

### **Step 2: Restart API Server**
```bash
# Stop current server (Ctrl+C)
# Start fresh
py -m uvicorn scraper.api.app:app --port 8002 --reload
```

---

### **Step 3: Test the API**

#### **A. List All Companies (Registry)**
```bash
curl http://localhost:8002/companies/registry
```

**Response:**
```json
{
  "total": 100,
  "skip": 0,
  "limit": 50,
  "count": 50,
  "companies": [
    {
      "symbol": "RELIANCE",
      "name": "Reliance Industries Ltd",
      "sector": "Energy",
      "status": "not_analyzed"  ← Shows "Analyze" button
    },
    {
      "symbol": "TCS",
      "name": "Tata Consultancy Services Ltd",
      "sector": "IT",
      "status": "not_analyzed"
    }
  ]
}
```

#### **B. Check Company Status**
```bash
curl http://localhost:8002/company/RELIANCE/status
```

**Response:**
```json
{
  "status": "not_analyzed",
  "message": "Company not yet analyzed"
}
```

#### **C. Trigger Analysis (On-Demand)**
```bash
curl -X POST http://localhost:8002/company/RELIANCE/analyze
```

**Response:**
```json
{
  "status": "queued",
  "message": "Analysis started. This may take a few minutes.",
  "symbol": "RELIANCE"
}
```

#### **D. Check Status Again (While Processing)**
```bash
curl http://localhost:8002/company/RELIANCE/status
```

**Response:**
```json
{
  "status": "processing",
  "message": "Analysis in progress"
}
```

#### **E. Check Status After Completion**
```bash
curl http://localhost:8002/company/RELIANCE/status
```

**Response:**
```json
{
  "status": "verified",
  "message": "Company data available"
}
```

---

## 🖥️ **Frontend Integration (Next Step)**

### **Update StocksPage.tsx**

```tsx
// Fetch from registry instead of companies
const response = await api.get('/companies/registry', {
  params: { skip, limit }
});

// Each company now has a status field
companies.forEach(company => {
  if (company.status === 'not_analyzed') {
    // Show "Analyze" button
  } else {
    // Show "View Details" link
  }
});
```

### **Add Analyze Button Component**

```tsx
function AnalyzeButton({ symbol }) {
  const [status, setStatus] = useState('idle');
  
  const handleAnalyze = async () => {
    setStatus('loading');
    await api.post(`/company/${symbol}/analyze`);
    
    // Poll for completion
    const interval = setInterval(async () => {
      const res = await api.get(`/company/${symbol}/status`);
      if (res.data.status === 'verified') {
        setStatus('complete');
        clearInterval(interval);
      }
    }, 5000);
  };
  
  if (status === 'loading') {
    return <Spinner>Analyzing...</Spinner>;
  }
  
  if (status === 'complete') {
    return <Link to={`/company/${symbol}`}>View Details</Link>;
  }
  
  return <Button onClick={handleAnalyze}>Analyze</Button>;
}
```

---

## ✅ **Benefits**

### **For You (Developer)**
- ✅ **No PC overload** - Registry seeds in 5 seconds
- ✅ **No overnight runs** - Ingestion happens on-demand
- ✅ **Safe testing** - Can't accidentally trigger 2000 ingestions
- ✅ **Gradual growth** - Database grows based on actual usage

### **For Users**
- ✅ **See all 100 companies immediately**
- ✅ **Click "Analyze" for companies they care about**
- ✅ **No fake data** - Only real ingested data shown
- ✅ **Transparent status** - Know what's available vs. pending

---

## 🚀 **Scaling Strategy**

### **Phase 1 (Today)**
- Seed 100 companies (Nifty 50 + Next 50)
- Users can analyze on-demand

### **Phase 2 (This Week)**
- Add 900 more companies to registry
- Still instant seeding
- Users analyze what they need

### **Phase 3 (Optional)**
- Night cron: Auto-analyze top 10 unanalyzed companies
- Gradual background growth
- No PC impact

---

## 🔒 **Safety Features**

### **1. Duplicate Prevention**
```python
if symbol in ingestion_locks:
    return {"status": "already_running"}
```

### **2. Already Analyzed Check**
```python
if company_exists(symbol):
    return {"status": "already_analyzed"}
```

### **3. Registry Validation**
```python
if not in_registry(symbol):
    raise HTTPException(404, "Not in registry")
```

---

## 📊 **Monitoring**

### **Check Registry Size**
```bash
mongo fundametrics --eval "db.companies_registry.count()"
```

### **Check Analyzed Companies**
```bash
mongo fundametrics --eval "db.companies.count()"
```

### **See Recent Analyses**
```bash
mongo fundametrics --eval "db.companies_registry.find({is_analyzed: true}).sort({analyzed_at: -1}).limit(5)"
```

---

## 🎬 **Next Steps**

1. **Run the seeder** (5 seconds)
2. **Restart API** (to load new routes)
3. **Test endpoints** (verify it works)
4. **Update frontend** (add Analyze button)
5. **Launch!** 🚀

---

## ❓ **FAQ**

**Q: What if user clicks Analyze and closes the page?**
A: Ingestion continues in background. Status API will show "verified" when done.

**Q: Can multiple users analyze the same company?**
A: No - locking prevents duplicates. Second user sees "already_running".

**Q: What if ingestion fails?**
A: Lock is released. User can retry. Error is logged.

**Q: How to add more companies to registry?**
A: Just add to NSE_COMPANIES list in seed_nse_registry.py and re-run.

---

## 🎉 **You're Ready!**

Run this now:
```bash
py seed_nse_registry.py
```

Then restart your API server and you're live with 100 companies! 🚀
