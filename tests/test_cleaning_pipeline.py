import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from scraper.utils.cleaner import DataCleaner
from scraper.utils.validator import DataValidator

def test_pipeline():
    # 1. Sample Raw Data (similar to what Screener/Trendlyne might return)
    raw_data = {
        "company_name": "Test Reliance ",
        "ratios": {
            "Market Cap": "₹ 1,50,000 Cr.",
            "Stock P/E": " 25.5 ",
            "ROE": " 15.2 % ",
            "ROCE": " 120.5 % ",
            "Dividend Yield": " 0.5 % ",
            "Face Value": " 10.00 "
        },
        "financial_tables": {
            "Profit & Loss": [
                {"Metric": "Net Profit", "Mar 2021": " 10,000 ", "Mar 2022": " 12,000 ", "Mar 2023": None}
            ]
        }
    }

    print("--- Phase 1: Cleaning ---")
    cleaner = DataCleaner()
    # Clean the nested structure
    cleaned_data = cleaner.clean_data(raw_data)
    
    # Normalize keys for the top level (optional, but good for DB)
    normalized_ratios = {cleaner.normalize_key(k): v for k, v in cleaned_data["ratios"].items()}
    print(f"Cleaned Ratios: {json.dumps(normalized_ratios, indent=2)}")

    print("\n--- Phase 2: Validation ---")
    validator = DataValidator()
    # The validator currently expects the original keys (as defined in the rules)
    # Let's run it on the cleaned data with original keys
    validated_data = validator.validate_stock_data(cleaned_data)
    
    report = validated_data["validation_report"]
    print(f"Validation Result: {'PASSED' if report['is_valid'] else 'FAILED'}")
    if report["errors"]:
        print(f"Errors: {report['errors']}")
    if report["warnings"]:
        print(f"Warnings: {report['warnings']}")

    # 3. Test Anomaly
    print("\n--- Phase 3: Testing Anomaly (High ROE) ---")
    bad_data = {
        "ratios": {
            "Market Cap": 5000,
            "ROE": 150.0  # Excessive
        },
        "financial_tables": {}
    }
    bad_validated = validator.validate_stock_data(bad_data)
    print(f"Anomaly Validation (ROE=150): {bad_validated['validation_report']['errors']}")

if __name__ == "__main__":
    test_pipeline()
