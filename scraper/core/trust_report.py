from datetime import datetime, timezone

def build_trust_report(symbol, run_id, coverage, warnings):
    """
    Build a trust report for a company after ingestion.
    
    Args:
        symbol: Company symbol
        run_id: Unique identifier for the ingestion run
        coverage: Coverage payload from ingestion
        warnings: List of warnings generated during metadata extraction
        
    Returns:
        dict: Trust report document
    """
    return {
        "symbol": symbol,
        "run_id": run_id,
        "coverage_score": coverage.get("score", coverage.get("coverage_ratio", 0) / 100 if "coverage_ratio" in coverage else 0),
        "available_blocks": coverage.get("available", []),
        "missing_blocks": coverage.get("missing", []),
        "warnings": warnings,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
