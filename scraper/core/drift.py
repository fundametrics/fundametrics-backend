from typing import List, Dict, Any, Optional
from decimal import Decimal
import statistics

def detect_drift(
    current_value: float,
    history_values: List[float],
    threshold_z: float = 3.0
) -> Dict[str, Any]:
    """
    Phase 17C: Drift Detection Engine.
    
    Args:
        current_value: The newly computed metric value.
        history_values: List of historical values (floats) for this metric.
        threshold_z: Z-score threshold to flag drift (default 3.0).
        
    Returns:
        Dictionary matching Drift JSON schema.
    """
    if not history_values:
        return {
            "detected": False,
            "reason": "Insufficient history",
            "drift_flag": False,
            "z_score": 0.0,
            "current_value": round(current_value, 2),
            "previous_value": None,
            "change_pct": 0.0,
            "classification": "new_metric",
            "confidence_impact": "neutral"
        }

    # Convert to floats for math
    history = [float(v) for v in history_values if v is not None]
    
    if len(history) < 2:
         return {
            "detected": False,
            "reason": "Insufficient history for stats",
            "drift_flag": False,
            "z_score": 0.0,
            "current_value": round(current_value, 2),
            "previous_value": round(history[0], 2) if history else None,
            "change_pct": 0.0,
            "classification": "developing_history",
            "confidence_impact": "neutral"
        }

    previous_value = history[0] # Assuming sorted desc, so [0] is latest history
    
    # Calculate Change %
    if previous_value == 0:
        change_pct = 0.0 if current_value == 0 else 100.0
    else:
        change_pct = ((current_value - previous_value) / abs(previous_value)) * 100.0

    # Calculate Stats
    try:
        mean = statistics.mean(history)
        stdev = statistics.stdev(history)
        
        if stdev == 0:
            z_score = 0.0 if current_value == mean else 99.9
        else:
            z_score = (current_value - mean) / stdev
    except Exception:
        z_score = 0.0

    is_drift = abs(z_score) > threshold_z
    
    reason = "Normal fluctuation"
    if is_drift:
        reason = f"Change exceeds {threshold_z}σ historical variance"

    return {
        "previous_value": round(previous_value, 2),
        "current_value": round(current_value, 2),
        "change_pct": round(change_pct, 2),
        "z_score": round(z_score, 2),
        "drift_flag": is_drift,
        "classification": "material_change" if is_drift else "normal",
        "reason": reason,
        "confidence_impact": "downgraded" if is_drift else "neutral"
    }
