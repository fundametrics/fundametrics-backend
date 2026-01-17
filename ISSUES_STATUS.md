# 🔧 THREE CRITICAL ISSUES - STATUS & ACTIONS

## 📋 ISSUE SUMMARY

| # | Issue | Status | Priority |
|---|-------|--------|----------|
| 1 | Registry stuck at 2,206 (should be 2,629) | 🔄 IN PROGRESS | 🔴 HIGH |
| 2 | Autopilot only 80-90/day (target 300/day) | ⏳ PENDING | 🟡 MEDIUM |
| 3 | Data missing for TATAMOTORS, TMCV, TMPV, ZOMATO | ⏳ PENDING | 🟡 MEDIUM |

---

## 🔄 ISSUE #1: REGISTRY SYNC (IN PROGRESS)

### Problem
- **Current:** 2,206 companies
- **Expected:** 2,629 companies  
- **Missing:** 423 companies

### Root Cause
Previous sync script (`update_latest_nse.py`) connected to DB but didn't complete the upsert loop.

### Solution Applied
Created `scripts/sync_registry_robust.py` with:
- ✅ Batch processing (100 companies at a time)
- ✅ Progress logging for each batch
- ✅ Error handling per batch
- ✅ Final count verification

### Status
🔄 **RUNNING NOW** - Script is processing batches

### Expected Result
```
New Companies Added:     423
Existing Updated:        2,206
Total in Registry:       2,629
```

---

## ⏳ ISSUE #2: AUTOPILOT RATE TOO LOW

### Problem
- **Target:** 300 companies/day (5 min intervals = 288/day)
- **Actual:** 80-90 companies/day
- **Shortfall:** ~210 companies/day

### Possible Causes
1. **API Rate Limiting (429 errors)**
   - Screener.in blocking requests
   - Need to check backend logs

2. **Ingestion Failures**
   - Some stocks failing to parse
   - Autopilot skips and continues

3. **Lock Contention**
   - Manual ingestions blocking autopilot

### Next Steps
1. **Check Render.com Logs:**
   ```
   - Go to Render dashboard
   - View finox-scraper logs
   - Search for "Autopilot" or "429" or "failed"
   ```

2. **If Rate Limited:**
   - Increase interval to 10 minutes (slower but safer)
   - Add exponential backoff

3. **If Parsing Errors:**
   - Log specific failures
   - Add fallback logic for edge cases

4. **If No Issues Found:**
   - Reduce interval to 3 minutes for 480/day

---

## ⏳ ISSUE #3: SPECIFIC STOCK DATA MISSING

### Problem Stocks
- **TATAMOTORS** - No data
- **TMCV** - No data
- **TMPV** - No data
- **ZOMATO** - No data

### Possible Causes
1. **Not in Registry Yet**
   - Will be fixed by Issue #1 sync

2. **Ingestion Failed**
   - Special characters in names
   - Missing data on source website
   - Different financial formats

3. **Not Analyzed Yet**
   - In registry but autopilot hasn't reached them

### Next Steps
1. **After Registry Sync:** Check if they're in registry
2. **Manual Test:** Try ingesting via admin panel
3. **Check Logs:** Look for specific error messages

### Manual Test Commands
```bash
# Via admin panel:
https://fundametrics.in/admin

# Or via API:
curl -X POST https://fundametrics-backend.onrender.com/api/admin/ingest \
  -H "x-admin-token: YOUR_TOKEN" \
  -d '{"symbol": "TATAMOTORS"}'
```

---

## 📊 TIMELINE

| Task | Duration | Status |
|------|----------|--------|
| Registry Sync | 5-10 min | 🔄 Running |
| Verify Registry Count | 1 min | ⏳ Pending |
| Check Autopilot Logs | 10 min | ⏳ Pending |
| Test Problem Stocks | 10 min | ⏳ Pending |
| Adjust Autopilot Rate | 5 min | ⏳ Pending |
| **Total** | **30-40 min** | **In Progress** |

---

## ✅ IMMEDIATE ACTIONS REQUIRED

### 1. Wait for Registry Sync to Complete (5 min)
The script is running. Once done, verify:
```bash
# Should show: Total in Registry: 2,629
```

### 2. Check Backend Logs (10 min)
```
1. Go to https://dashboard.render.com
2. Select finox-scraper service
3. Click "Logs" tab
4. Search for:
   - "Autopilot" (to see ingestion attempts)
   - "429" (rate limiting)
   - "failed" (errors)
   - "TATAMOTORS" (specific stock issues)
```

### 3. Test Problem Stocks Manually (10 min)
```
1. Go to https://fundametrics.in/admin
2. Enter admin token
3. Try ingesting: TATAMOTORS, TMCV, TMPV, ZOMATO
4. Note any error messages
```

---

## 🎯 SUCCESS CRITERIA

- ✅ Registry count = 2,629
- ✅ Autopilot rate = 250-300/day
- ✅ All 4 problem stocks have data or clear error reason

---

**Current Status:** Registry sync running, awaiting completion...
