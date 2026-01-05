
import json
import logging
import json
import logging
from scraper.core.metrics_engine import FundametricsMetricsEngine
from scraper.core.ratios_engine import FundametricsRatiosEngine

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Load the failing BHEL data
try:
    with open('debug_bhel_success.json', 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print("Could not find debug_bhel_success.json. Please ensure it exists.")
    exit(1)

# Extract inputs for compute_fundametrics_metrics
# Note: debug_bhel_success.json is the FINAL output, so we need to reconstruct 
# what the inputs were. The 'financials' key likely holds the canonical data 
# that validly passed to the API response builder.

canon = data.get("financials", {})
meta = data.get("metadata", {}) or {}
constants = meta.get("constants") or {}

income_statement = canon.get("income_statement") or {}
balance_sheet = canon.get("balance_sheet") or {}

# Try to replicate the extraction logic from api_response_builder.py
# 1. Shares Outstanding
shares_outstanding = constants.get("shares_outstanding")
if shares_outstanding is None:
    face_value = constants.get("face_value")
    # Simulate the fallback logic I added
    if not face_value:
        # Check if Face Value is deep inside ratios table? 
        # The output JSON structure might be slightly different than internal state, 
        # but let's try to find where face_value is.
        ratios_table = canon.get("ratios_table") or {}
        # print("Ratios Table Keys:", ratios_table.keys())
        # In the output JSON, ratios_table values are dicts/objects.
    
    # Let's assume for BHEL we know it should be 2.0. 
    # But wait, I want to reproduce the FAILURE.
    pass

share_price_block = meta.get("price") or {}
share_price = share_price_block.get("value")
if share_price is None:
    share_price = constants.get("share_price")

print(f"DEBUG: Share Price: {share_price}")
print(f"DEBUG: Shares Outstanding: {shares_outstanding}")
print(f"DEBUG: Income Statement Periods: {list(income_statement.keys())}")
print(f"DEBUG: Balance Sheet Periods: {list(balance_sheet.keys())}")

# Instantiate Engine
engine = FundametricsMetricsEngine()

print("\n--- ATTEMPTING COMPUTATION ---")
try:
    results = engine.compute_fundametrics_metrics(
        income_statement=income_statement,
        balance_sheet=balance_sheet,
        shares_outstanding=shares_outstanding,
        share_price=share_price 
    )
    print("Computation Result Keys:", list(results.keys()))
    print("Computation Result Values:", results)
except Exception as e:
    print(f"!!! CRASH !!! {e}")
    import traceback
    traceback.print_exc()
