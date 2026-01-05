import logging
from typing import Any, Dict
from scraper.utils.cleaner import DataCleaner
from scraper.utils.validator import DataValidator
from scraper.utils.logger import get_logger

log = get_logger(__name__)

class DataPipeline:
    """
    Coordinates the cleaning and validation of scraped data.
    """

    def __init__(self):
        self.cleaner = DataCleaner()
        self.validator = DataValidator()

    def process_stock_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs the full pipeline:
        1. Keeps raw data
        2. Produces cleaned data
        3. Validates and flags
        """
        symbol = raw_data.get("symbol", "UNKNOWN")
        log.info(f"Processing data for {symbol}")

        # 1. Clean Data
        cleaned_data = self.cleaner.clean_data(raw_data)
        
        # 2. Add raw data context (keeping a copy of raw for auditing)
        result = {
            "symbol": symbol,
            "raw_data": raw_data,
            "cleaned_data": cleaned_data
        }

        # 3. Validate
        validated_data = self.validator.validate_stock_data(cleaned_data)
        result["validation_report"] = validated_data.get("validation_report")
        
        return result
