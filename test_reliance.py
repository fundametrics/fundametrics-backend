import requests
import json

# Test Reliance API endpoint
url = "http://localhost:8000/api/company/RELIANCE"

try:
    response = requests.get(url)
    data = response.json()
    
    print("=" * 80)
    print("RELIANCE DATA CHECK")
    print("=" * 80)
    
    # Check shareholding
    shareholding = data.get("shareholding", {})
    print(f"\n📊 SHAREHOLDING STATUS: {shareholding.get('status', 'NOT FOUND')}")
    
    if shareholding.get("status") == "available":
        print(f"   ✓ Summary keys: {list(shareholding.get('summary', {}).keys())}")
        print(f"   ✓ History records: {len(shareholding.get('history', []))}")
        print(f"   ✓ Insights: {len(shareholding.get('insights', []))}")
    else:
        print(f"   ✗ Shareholding data not available")
        print(f"   Raw shareholding: {json.dumps(shareholding, indent=2)[:500]}")
    
    # Check news
    news = data.get("news", [])
    print(f"\n📰 NEWS STATUS: {len(news)} articles found")
    
    if news:
        print(f"   ✓ Latest: {news[0].get('title', 'N/A')[:60]}...")
        print(f"   ✓ Source: {news[0].get('source', 'N/A')}")
    else:
        print(f"   ✗ No news articles found")
    
    # Check other key data
    print(f"\n📈 OTHER DATA:")
    print(f"   Company name: {data.get('company', {}).get('name', 'N/A')}")
    print(f"   Metrics count: {len(data.get('fundametrics_metrics', []))}")
    print(f"   Yearly financials keys: {list(data.get('yearly_financials', {}).keys())}")
    
    print("\n" + "=" * 80)
    
except Exception as e:
    print(f"ERROR: {e}")
