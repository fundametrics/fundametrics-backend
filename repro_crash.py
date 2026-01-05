import json
import os
import sys

# Add parent dir to sys.path
sys.path.append(os.getcwd())

from scraper.core.metrics_engine import FundametricsMetricsEngine
from scraper.core.metrics import MetricValue

# Load data
with open('data/processed/bhel/latest.json', 'r') as f:
    d = json.load(f)

fr = d.get('fundametrics_response', {})
can = fr.get('financials', {})
is_stmt = can.get('income_statement', {})
bs_stmt = can.get('balance_sheet', {})
meta = fr.get('metadata', {})
const = meta.get('constants', {})

# We need objects for compute_metric_values if it expects them
# Actually, the builder usually passes the raw dicts from canonical_financials
# In build(), they were MetricValue objects.

engine = FundametricsMetricsEngine()

# Reconstruct MetricValue objects if they are dicts in JSON
def rescore(data):
    if not isinstance(data, dict): return data
    res = {}
    for p, row in data.items():
        res[p] = {}
        for m, v in row.items():
            if isinstance(v, dict) and 'value' in v:
                res[p][m] = MetricValue(
                    value=v.get('value'),
                    unit=v.get('unit', ''),
                    statement_id=v.get('statement_id'),
                    computed=v.get('computed', False)
                )
            else:
                res[p][m] = v
    return res

is_obj = rescore(is_stmt)
bs_obj = rescore(bs_stmt)

print("Running compute_metric_values...")
try:
    mv = engine.compute_metric_values(
        income_statement=is_obj,
        balance_sheet=bs_obj,
        shares_outstanding=348.2, # dummy
        share_price=282.0,
        metadata=meta
    )
    print("Success! Metrics count:", len(mv))
except Exception as e:
    import traceback
    traceback.print_exc()
