def get_disclaimer_text(trust_grade: str) -> str:
    """
    Phase 18E: Safety Controls - Hard Disclaimers.
    """
    if trust_grade == "A":
        return "Fundametrics Verified: High confidence data verified against multiple disclosures."
    elif trust_grade == "B":
        return "Reliable: Standard calculation based on latest annual reports."
    elif trust_grade == "C":
        return "Caution: Data may be stale or inconsistent. Verify with official filings."
    else:
        return "Risk: Low confidence metric. Significant drift or missing inputs detected. Do not rely for investment."

def check_feature_eligibility(feature: str, trust_score_dict: dict) -> bool:
    """
    Phase 18E: Feature gating based on trust.
    """
    grade = trust_score_dict.get('grade', 'D')
    flags = trust_score_dict.get('flags', []) # Hypothetical extra flags
    
    if feature == "highlight":
        # Don't highlight low trust metrics
        return grade in ["A", "B"]
        
    if feature == "compare":
        # Don't allow comparison if grade is D
        return grade != "D"
        
    return True
