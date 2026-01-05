from typing import Dict, Any, Optional

def can_compare(
    metric_a: Dict[str, Any],
    metric_b: Dict[str, Any],
    confidence_tolerance: float = 0.15
) -> Dict[str, Any]:
    """
    Phase 18B: Metric Comparison Integrity Engine.
    
    Determines if two metrics can be validly compared based on strict financial integrity rules.
    
    Args:
        metric_a: First metric dictionary (metric_name, unit, confidence, source_provenance, etc.)
        metric_b: Second metric dictionary.
        confidence_tolerance: Max allowed difference in confidence scores (default 15%).
        
    Returns:
        JSON result: { "comparable": bool, "reason": str|None }
    """
    
    # 1. Metric Name identity
    if metric_a.get('metric_name') != metric_b.get('metric_name'):
         return {"comparable": False, "reason": "Different metric names"}

    # 2. Unit identity
    if metric_a.get('unit') != metric_b.get('unit'):
        return {"comparable": False, "reason": f"Unit mismatch: {metric_a.get('unit')} vs {metric_b.get('unit')}"}
        
    # 3. Drift Blocks
    if _has_drift(metric_a) or _has_drift(metric_b):
        return {"comparable": False, "reason": "Active drift flag detected on one or more metrics"}

    # 4. Confidence Similarity
    conf_a = float(metric_a.get('confidence', 0))
    conf_b = float(metric_b.get('confidence', 0))
    if abs(conf_a - conf_b) > confidence_tolerance:
        return {"comparable": False, "reason": f"Confidence disparity > {int(confidence_tolerance*100)}%"}
        
    # 5. Statement Scope (Consolidated vs Standalone)
    # Extract scope from provenance or explainability
    scope_a = _extract_scope(metric_a)
    scope_b = _extract_scope(metric_b)
    
    if scope_a and scope_b and scope_a != scope_b:
        return {"comparable": False, "reason": f"Scope mismatch: {scope_a} vs {scope_b}"}

    return {"comparable": True, "reason": None}

def _has_drift(metric: Dict[str, Any]) -> bool:
    drift = metric.get('drift')
    if drift and isinstance(drift, dict):
        return drift.get('drift_flag', False)
    return False

def _extract_scope(metric_data: Dict[str, Any]) -> Optional[str]:
    """
    Attempts to find statement scope (Consolidated/Standalone) 
    from provenance or explainability.
    """
    # Try Provenance first (Phase 17D standard)
    prov = metric_data.get('source_provenance')
    if prov and isinstance(prov, dict):
        inputs = prov.get('inputs_provenance', [])
        # Iterate inputs to find a scope. 
        # Usually all inputs should match, but we take the first definite one.
        for inp in inputs:
            src = inp.get('source')
            if src and src.get('statement_scope'):
                return src.get('statement_scope')
                
    # Fallback/Alternative paths could be added here
    return None
