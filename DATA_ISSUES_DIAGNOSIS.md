# 🔧 DATA & AUTOPILOT ISSUES - DIAGNOSIS & FIXES

## 🔴 REPORTED ISSUES

### 1. Data Issues in Specific Stocks
- **TATAMOTORS** - Data missing or incomplete
- **TMCV** - Data missing or incomplete  
- **TMPV** - Data missing or incomplete
- **ZOMATO** - Data missing or incomplete

### 2. Registry Count Stuck at 2206
- Expected: **2,629 companies** (from NSE EQUITY_L.csv)
- Actual: **2,206 companies**
- **Gap: 423 companies missing**

### 3. Autopilot Ingestion Rate Too Low
- **Target:** 300 companies/day (5 min intervals)
- **Actual:** 80-90 companies/day
- **Gap:** 210-220 companies/day shortfall

---

## 🔍 ROOT CAUSES

### Issue #1: Registry Sync Script Didn't Complete
The `scripts/update_latest_nse.py` I ran earlier **connected to DB but didn't finish**.

**Evidence:**
- Command output showed "Connected to DB: fundametrics" but no completion message
- Exit code couldn't be determined
- No "Registry Update Complete" log

**Why it failed:**
- Likely network timeout or connection drop during the 2,600 upsert operations
- Script was running synchronously (slow for remote MongoDB)

### Issue #2: Autopilot Rate Limiting
**Possible causes:**
1. **API Rate Limits (429 errors)**
   - Screener.in might be blocking requests
   - Need to check backend logs for 429 responses

2. **Errors During Ingestion**
   - Some stocks might be failing to parse
   - Autopilot continues but skips failed ones

3. **Lock Contention**
   - If manual ingestions are running, autopilot skips

### Issue #3: Specific Stock Data Problems
**TATAMOTORS, TMCV, TMPV, ZOMATO** might have:
- Special characters in names causing parsing errors
- Missing data on source website
- Different financial statement formats

---

## ✅ SOLUTIONS

### Fix #1: Complete Registry Sync (PRIORITY 1)

I'll create a **robust batch sync script** with:
- Batch processing (100 companies at a time)
- Progress logging
- Error handling
- Resume capability

**Action Required:**
```bash
cd finox-scraper
python scripts/sync_registry_robust.py
```

This will:
1. Fetch all 2,629 companies from NSE
2. Upsert in batches of 100
3. Show progress every batch
4. Complete in ~2-3 minutes

### Fix #2: Increase Autopilot Rate (PRIORITY 2)

**Option A: Reduce Interval (Aggressive)**
Change `scheduler.py` line 100:
```python
# From:
IntervalTrigger(minutes=5)  # 288/day

# To:
IntervalTrigger(minutes=3)  # 480/day
```

**Option B: Add Error Logging**
Add detailed logging to see why ingestions are failing:
```python
logger.error(f"❌ Autopilot failed for {target_symbol}: {e}", exc_info=True)
```

**Option C: Check Backend Logs**
SSH into Render.com and check logs:
```bash
# Look for:
# - 429 Too Many Requests
# - Parsing errors
# - Timeout errors
```

### Fix #3: Investigate Specific Stock Failures

**Manual Test:**
Try ingesting each problem stock manually via admin panel:
1. Go to `/admin`
2. Try ingesting: TATAMOTORS, TMCV, TMPV, ZOMATO
3. Check error messages

**Common Issues:**
- **TATAMOTORS** - Might have "Tata Motors Ltd" vs "TATAMOTORS" mismatch
- **TMCV/TMPV** - Might be delisted or suspended
- **ZOMATO** - New listing, might have incomplete historical data

---

## 🚀 IMMEDIATE ACTION PLAN

### Step 1: Run Registry Sync (5 minutes)
```bash
cd c:/Users/Laser cote/.gemini/antigravity/scratch/finox-scraper
python scripts/sync_registry_robust.py
```

**Expected Result:**
- Registry count: 2,206 → 2,629 (+423)

### Step 2: Check Autopilot Logs (2 minutes)
```bash
# On Render.com dashboard:
# 1. Go to your finox-scraper service
# 2. Click "Logs"
# 3. Search for "Autopilot" in last 24 hours
# 4. Look for error patterns
```

### Step 3: Test Problem Stocks (5 minutes)
```bash
# Via admin panel at fundametrics.in/admin
# Or via API:
curl -X POST https://fundametrics-backend.onrender.com/api/admin/ingest \
  -H "x-admin-token: YOUR_TOKEN" \
  -d '{"symbol": "TATAMOTORS"}'
```

### Step 4: Adjust Autopilot Rate (1 minute)
If no errors found, reduce interval to 3 minutes for faster ingestion.

---

## 📊 EXPECTED TIMELINE

| Task | Duration | Result |
|------|----------|--------|
| Registry Sync | 5 min | +423 companies |
| Log Analysis | 10 min | Identify autopilot issues |
| Fix Autopilot | 5 min | 80/day → 300/day |
| Test Problem Stocks | 10 min | Identify data issues |
| **Total** | **30 min** | **All issues diagnosed** |

---

## 🔧 FILES TO CREATE

I'll create the robust registry sync script next.
