import asyncio
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from .explainability import build_explainability
from .drift import detect_drift
from .trust import calculate_trust_score

class MetricEngine:
    def __init__(self, agent_name="Fundametrics Metric Engine v2.0"):
        self.agent_name = agent_name

    def compute_metric(
        self,
        metric_name: str,
        value: float,
        inputs: List[Dict[str, Any]],
        formula: str,
        historical_values: List[float],
        base_confidence: float = 1.0,
        assumptions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates 17A, 17B, 17C, 17D, 17E to produce a full Phase 17 compliant metric.
        
        Args:
            metric_name: e.g. "Operating Margin"
            value: The computed raw value.
            inputs: List of inputs with source provenance.
            formula: Explanation formula.
            historical_values: List of floats for drift detection.
            base_confidence: Initial confidence (default 1.0).
            assumptions: List of assumptions strings.
            
        Returns:
            Dictionary ready to be assigned to ComputedMetric model fields.
        """
        
        # 1. Explainability (17B)
        # Transform inputs to simple dict for Builder if needed, but Builder expects specific format
        # Let's assume 'inputs' coming here has {name, value, statement_id/source}
        explainability = build_explainability(
            metric_name=metric_name,
            inputs=inputs,
            formula=formula,
            assumptions=assumptions
        )
        
        # 2. Drift (17C)
        drift = detect_drift(
            current_value=value,
            history_values=historical_values
        )
        
        # 3. Trust (17E)
        # Determine freshness from inputs
        # Find oldest 'scraped_at'
        freshness_days = 0
        try:
            dates = [
                datetime.fromisoformat(inp['source']['scraped_at']) 
                for inp in inputs 
                if inp.get('source') and inp['source'].get('scraped_at')
            ]
            if dates:
                oldest = min(dates)
                freshness_days = (datetime.utcnow() - oldest).days
        except Exception:
            pass # Default 0
            
        trust = calculate_trust_score(
            confidence=base_confidence,
            drift_result=drift,
            source_freshness_days=freshness_days
        )
        
        # 4. Provenance (17D) - Aggregated
        source_provenance = {
            "calculation_agent": self.agent_name,
            "computed_at": datetime.utcnow().isoformat(),
            "inputs_provenance": [
                 {
                     "metric": inp['name'],
                     "source": inp.get('source')
                 }
                 for inp in inputs
            ]
        }
        
        # 5. Final Assembly
        return {
            "value": Decimal(str(value)),
            "unit": "%", # Default, should arguably be passed in
            "confidence": Decimal(str(base_confidence)),
            "reason": drift['reason'], # Use drift reason as primary high-level reason
            "explainability": explainability,
            "drift": drift,
            "source_provenance": source_provenance,
            "trust_score": trust,
            "integrity": "verified" if not drift['drift_flag'] else "warning"
        }
