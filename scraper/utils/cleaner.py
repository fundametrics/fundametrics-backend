import re
import logging
from typing import Any, Dict, List, Union, Optional

log = logging.getLogger(__name__)

class DataCleaner:
    """
    Utility class for cleaning and normalizing scraped financial data.
    """

    @staticmethod
    def clean_numeric(value: Any) -> Optional[Union[float, int]]:
        """
        Normalizes a string or numeric value into a clean float or int.
        Removes symbols (₹, %, commas), whitespace, and handles 'Cr.' units.
        """
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            return value

        if not isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        # Cleaning process
        # 1. Remove commas, currency symbols, and percentage signs
        clean_str = re.sub(r'[₹%,]', '', value).strip()
        
        # 2. Handle 'Cr' or 'Cr.' suffixes
        is_crore = False
        if re.search(r'Cr\.?$', clean_str, re.I):
            is_crore = True
            clean_str = re.sub(r'Cr\.?$', '', clean_str, flags=re.I).strip()

        # 3. Handle empty after cleaning
        if not clean_str:
            return None

        # 4. Conversion
        try:
            # Check if it's a number
            if '.' in clean_str:
                num = float(clean_str)
            else:
                num = int(clean_str)
            
            # If it was in Crores, we keep it as is if that's the base unit we want,
            # but usually for a 'normalization' phase, we might want to standardize.
            # However, Indian markets often talk in Crores. Let's keep it as the value
            # and let the validator/storage handle units if needed. 
            # (In this project, external financial data values are usually in Cr by default).
            
            return num
        except ValueError:
            # Check for '-' or 'N/A'
            if clean_str in ('-', 'N/A', 'NaN', ''):
                return None
            log.debug(f"Could not convert string to numeric: {value}")
            return None

    @classmethod
    def clean_data(cls, data: Any) -> Any:
        """
        Recursively cleans a dictionary or list of data.
        Attempts to convert all string values to numeric where possible.
        """
        if isinstance(data, dict):
            return {k: cls.clean_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.clean_data(i) for i in data]
        elif isinstance(data, str):
            # Try numeric cleaning
            numeric_val = cls.clean_numeric(data)
            return numeric_val if numeric_val is not None else data.strip()
        else:
            return data

    @staticmethod
    def normalize_key(key: str) -> str:
        """
        Normalizes dictionary keys (lowercase, snake_case, removes special characters).
        Example: "Market Cap" -> "market_cap", "Price_Earnings" -> "price_earnings"
        """
        k = key.lower().strip()
        k = k.replace('/', '_per_').replace('&', '_and_')
        k = re.sub(r'[^a-z0-9_]', '_', k)
        k = re.sub(r'_+', '_', k)
        return k.strip('_')
