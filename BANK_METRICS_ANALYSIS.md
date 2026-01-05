# Bank Metrics Analysis - HDFC, ICICI, SBI, Kotak, Bajaj Finance

## Issue Summary
Banks and NBFCs (Non-Banking Financial Companies) like HDFC Bank, ICICI Bank, SBI, Kotak Bank, and Bajaj Finance **do not have "Operating Margin"** in the traditional sense because:

1. **Banks are financial institutions**, not manufacturing/service companies
2. They don't have "Operating Profit" - instead they have:
   - **Net Interest Income (NII)**
   - **Net Interest Margin (NIM)** - this is the banking equivalent of operating margin
   - **Fee Income**
   - **Other Income**

## What Metrics ARE Available for Banks?

Based on database inspection, banks typically have:

### ✅ Available Metrics:
- **ROE** (Return on Equity) - fundametrics_return_on_equity
- **ROCE** (Return on Capital Employed) - fundametrics_return_on_capital_employed  
- **Debt to Equity** - fundametrics_debt_to_equity ✅ (This EXISTS in DB)
- **P/E Ratio** - fundametrics_price_to_earnings
- **Book Value** - fundametrics_book_value
- **Dividend Yield** - fundametrics_dividend_yield
- **EPS** - fundametrics_eps
- **Face Value** - fundametrics_face_value

### ❌ NOT Available for Banks:
- **Operating Margin** (OPM) - Banks don't have this metric
- **Operating Profit** - Not applicable to banks

## Current Status

### ✅ WORKING:
- **Maruti Suzuki**: Has both Operating Margin (10.75%) and Debt to Equity (0.0) ✅
- **TCS**: All metrics working ✅

### ❌ MISSING (Expected Behavior):
- **HDFC Bank, ICICI Bank, SBI, Kotak Bank, Bajaj Finance**: 
  - **Operating Margin**: NULL/None (EXPECTED - banks don't have this)
  - **Debt to Equity**: Should be visible but showing NULL (BUG)

## Root Cause

The `Debt to Equity` metric EXISTS in the database as `fundametrics_debt_to_equity` but is not appearing in the API response. This suggests an issue in the transformation layer (`mongo_routes.py`).

## Solution

1. **For "Debt to Equity"**: Fix the API transformation to correctly map `fundametrics_debt_to_equity` → "Debt To Equity"
2. **For "Operating Margin"**: Accept that banks will show NULL/— for this metric (this is correct behavior)
3. **Alternative**: Consider showing "Net Interest Margin" for banks instead of "Operating Margin"

## Recommendation

For the frontend, you should:
1. Display "—" or "N/A" for Operating Margin on bank pages (this is expected)
2. Ensure Debt to Equity shows the actual value from the database
3. Consider adding bank-specific metrics like "NIM" or "CASA Ratio" in the future
