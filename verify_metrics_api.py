import requests
import json
import time

def check_metrics(symbol):
    try:
        print(f"\n--- Checking {symbol} ---")
        # In this phase, we are hitting the python backend directly to verifying transformation logic
        r = requests.get(f'http://localhost:8002/stocks/{symbol}')
        d = r.json()
        metrics = d.get('fundametrics_metrics', [])
        
        opm = next((m for m in metrics if m['metric_name'] == 'Operating Margin'), None)
        debt = next((m for m in metrics if m['metric_name'] == 'Debt To Equity'), None)
        
        print(f"Operating Margin: {opm['value'] if opm else 'MISSING'}")
        print(f"Debt To Equity: {debt['value'] if debt else 'MISSING'}")
        
    except Exception as e:
        print(f"Error checking {symbol}: {e}")

if __name__ == "__main__":
    for s in ['HDFCBANK', 'ICICIBANK', 'SBIN', 'MARUTI', 'BAJFINANCE', 'KOTAKBANK']:
        check_metrics(s)
