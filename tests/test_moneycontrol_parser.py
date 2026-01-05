import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scraper.sources.moneycontrol_parser import MoneycontrolParser

def test_mc_parser():
    file_path = "mc_reliance.txt"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found. Run save_mc_html.py first.")
        return

    with open(file_path, "r", encoding='utf-8') as f:
        html = f.read()

    parser = MoneycontrolParser(html, symbol="RELIANCE")
    data = parser.parse_all()

    print(json.dumps(data, indent=2))
    
    # Assertions
    assert data["company_name"] == "Reliance Industries Ltd."
    assert data["sector"] == "Oil & Gas"
    assert data["industry"] == "Oil Exploration and Production"
    assert len(data["management"]) > 0
    assert data["management"][0]["name"] == "Mukesh D Ambani"
    
    print("\n[SUCCESS] MoneycontrolParser verified successfully!")

if __name__ == "__main__":
    test_mc_parser()
