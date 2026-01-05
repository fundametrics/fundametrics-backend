from typing import Dict, Any

def calculate_trust_score(
    confidence: float,
    drift_result: Dict[str, Any],
    source_freshness_days: int
) -> Dict[str, Any]:
    """
    Phase 17E: Trust Score Engine.
    
    Args:
        confidence: Base confidence score (0.0 to 1.0) from Phase 17A.
        drift_result: Output from drift detection.
        source_freshness_days: Age of data in days.
        
    Returns:
        Trust JSON object.
    """
    
    # 1. Base Score (0-100)
    score = confidence * 100.0
    
    components = {
        "confidence": round(score, 1),
        "drift_penalty": 0,
        "source_weight": 0, # Default source weight
        "freshness": 0
    }
    
    # 2. Drift Penalty
    if drift_result.get("drift_flag", False):
        penalty = 15 # Severe penalty for unexplained drift
        score -= penalty
        components["drift_penalty"] = -penalty
        
    # 3. Freshness Bonus/Penalty
    if source_freshness_days < 10:
        bonus = 5
        score += bonus
        components["freshness"] = bonus
    elif source_freshness_days > 90:
        penalty = 10
        score -= penalty
        components["freshness"] = -penalty
        
    # Cap Score
    score = max(0, min(100, score))
    
    # Grade
    if score >= 90:
        grade = "A"
        label = "Highly reliable"
    elif score >= 75:
        grade = "B"
        label = "Reliable"
    elif score >= 60:
        grade = "C"
        label = "Use with caution"
    else:
        grade = "D"
        label = "Weak trust"

    return {
        "score": round(score),
        "grade": grade,
        "label": label,
        "components": components,
        "overall": label  # Mapping to Phase 17E request "overall" field
    }
