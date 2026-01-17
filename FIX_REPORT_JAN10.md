# 🔧 FIXES APPLIED & DIAGNOSIS REPORT

## 1. ✅ Data Issues (TATAMOTORS, etc.)
**Status: Fixed Incorrect Mapping**
- **Root Cause:** `scraper/sources/screener.py` had an incorrect mapping: `TATAMOTORS` -> `TMCV`. This caused it to look for a non-existent or invalid symbol `TMCV` instead of `TATAMOTORS`.
- **Fix:** Removed the mapping. The system will now correctly query `screener.in/company/TATAMOTORS/`.
- **Verification:** Test ingestion runs without error, extracting data. (Metrics count might depend on data availability, but connection is fixed).

## 2. ✅ Autopilot Rate (80/day -> 300/day)
**Status: Rate Increased**
- **Problem:** User reported ~80-90 ingestions/day.
- **Root Cause:** Scheduler interval was 5 minutes (288/day max). With failures/skips, this resulted in <100.
- **Fix:** Reduced interval to **2 minutes** (~720 attempts/day).
- **Impact:** Even with 50% success rate, you should hit >300 ingestions/day.

## 3. 🔄 Registry Count (2206 vs 2629)
**Status: Sync in Progress**
- **Current Count:** 2,242 (+36 from reported)
- **Action:** A robust sync script is running to fetch the remaining ~400 companies.
- **Note:** NSE archives can be slow. The script processes in batches. If it stops, it can be re-run; it is safe (upsert).

---

## 🚀 RECOMMENDATIONS

### For Immediate Data Fix:
1.  **Restart the Scraper Service:** (If running via Docker/Systemd) to apply the code changes (Scheduler update + Mapping fix).
2.  **Manually Ingest Problem Stocks:**
    Go to Admin Panel -> Ingest:
    - `TATAMOTORS`
    - `ZOMATO`
    - `TATAMTRDVR` (if you meant TMCV/TMPV to be Tata Motors DVR)

### For "TMCV" / "TMPV":
- These do not appear to be standard NSE symbols.
- If they are **Tata Motors DVR**, please use symbol: **`TATAMTRDVR`**.
- If they are distinct entities, please provide the full company name or ISIN.

### Monitoring:
- Check `companies_registry` count in MongoDB after ~1 hour. It should reach ~2600.
- Check Autopilot logs for increased activity.
