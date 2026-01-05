import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

class DataValidator:
    """
    Validation engine for Fundametrics raw facts.
    Ensures required metadata and financial coverage exist before storage.
    """

    def validate_metadata(self, metadata: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        if not metadata.get("company_name"):
            warnings.append("Company name missing in metadata")

        if not metadata.get("symbol"):
            warnings.append("Symbol missing in metadata")

        constants = metadata.get("constants", {}) or {}
        if constants.get("shares_outstanding") in (None, ""):
            warnings.append("Shares outstanding not available")

        return errors, warnings

    def validate_financials(self, financials: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []

        income_statement = financials.get("income_statement", {}) or {}
        if not income_statement:
            errors.append("Income statement data is missing")
            return errors, warnings

        # Ensure most recent period has revenue and net income facts
        periods = sorted(income_statement.keys())
        latest_period = periods[-1] if periods else None
        if latest_period:
            latest_data = income_statement.get(latest_period, {})
            if latest_data.get("revenue") in (None, ""):
                warnings.append(f"Revenue missing for period {latest_period}")
            if latest_data.get("net_income") in (None, ""):
                warnings.append(f"Net income missing for period {latest_period}")

        return errors, warnings

    def validate_stock_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full validation wrapper for a stock data object.
        Adds a 'validation_report' key to the data.
        """
        report = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "flags": []
        }

        metadata_errors, metadata_warnings = self.validate_metadata(data.get("metadata", {}))
        report["errors"].extend(metadata_errors)
        report["warnings"].extend(metadata_warnings)

        fin_errors, fin_warnings = self.validate_financials(data.get("financials", {}))
        report["errors"].extend(fin_errors)
        report["warnings"].extend(fin_warnings)

        if report["errors"]:
            report["is_valid"] = False
            report["flags"].append("CRITICAL_ERRORS")
        elif report["warnings"]:
            report["flags"].append("WARNINGS_FOUND")

        data["validation_report"] = report
        return data
