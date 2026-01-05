from typing import List, Dict, Optional, Any

def build_explainability(
    metric_name: str,
    inputs: List[Dict[str, Any]],
    formula: str,
    assumptions: Optional[List[str]] = None,
    limitations: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Constructs the explainability JSON object for a computed metric.
    
    Args:
        metric_name: Name of the metric (e.g., "Operating Margin").
        inputs: List of input dictionaries with name, value, and statement info.
        formula: String representation of the formula used.
        assumptions: List of assumptions made during calculation.
        limitations: List of known limitations.
        
    Returns:
        Dictionary matching the Phase 17B Explainability schema.
    """
    
    # Auto-derive limitations if not provided (Phase 17B requirement)
    if limitations is None:
        limitations = _derive_default_limitations(metric_name)
        
    return {
        "why_available": True, # If we are building this, it is available
        "formula": formula,
        "inputs_used": inputs,
        "assumptions": assumptions or [],
        "limitations": limitations
    }

def _derive_default_limitations(metric_name: str) -> List[str]:
    """
    Returns specific standard limitations based on metric type.
    """
    common = ["Based on disclosed statements only"]
    
    if "Margin" in metric_name:
        return common + ["Does not account for non-operating exceptional items unless specified"]
    elif "Growth" in metric_name:
        return common + ["Sensitive to base effect"]
    
    return common

def build_blocked_explainability(reason: str, missing_inputs: List[str]) -> Dict[str, Any]:
    """
    Returns explainability object for a blocked/unavailable metric.
    """
    return {
        "why_available": None,
        "why_unavailable": reason,
        "blocked_because": "missing_inputs",
        "inputs_missing": missing_inputs
    }
