"""
Fundametrics Shareholding Audit Module
==============================

This module handles the legal audit and normalization of shareholding data.
It ensures compliance by only tracking permitted categories and validating data integrity.
"""

from typing import Dict, List, Optional, Tuple, TypedDict
from dataclasses import dataclass
from datetime import datetime
import logging

log = logging.getLogger(__name__)

class ShareholdingData(TypedDict):
    """Normalized shareholding data structure"""
    promoter: Optional[float]
    fii: Optional[float]
    dii: Optional[float]
    public: Optional[float]
    government: Optional[float]
    other: Optional[float]

@dataclass
class ShareholdingAnomaly:
    """Represents a detected anomaly in shareholding data"""
    period: str
    issue: str
    details: str
    severity: str  # 'warning' or 'error'

class ShareholdingAudit:
    """
    Performs legal audit and normalization of shareholding data.
    Ensures compliance with data handling requirements.
    """
    
    # Allowed shareholding categories (case-insensitive)
    ALLOWED_CATEGORIES = {
        'promoter', 'promoters', 'promoter group',
        'institutional', 'institutions', 'institutional investors',
        'fii', 'fiis', 'foreign institutions',
        'dii', 'diis', 'domestic institutions',
        'public', 'public shareholders', 'public shareholding',
        'government', 'government of india', 'gov',
        'other', 'others'
    }
    
    # Mapping of common variations to standard categories
    CATEGORY_MAPPING = {
        'promoters': 'promoter',
        'promoter group': 'promoter',
        'institutions': 'fii',  # Default to fii or keep as institutional if we want broad
        'institutional investors': 'fii',
        'fii': 'fii',
        'fiis': 'fii',
        'foreign institutions': 'fii',
        'dii': 'dii',
        'diis': 'dii',
        'domestic institutions': 'dii',
        'public shareholders': 'public',
        'public shareholding': 'public',
        'government of india': 'government',
        'gov': 'government',
        'others': 'other'
    }
    
    def __init__(self):
        self.anomalies: List[ShareholdingAnomaly] = []
    
    def normalize_shareholding_data(self, raw_data: Dict) -> Dict[str, ShareholdingData]:
        """
        Normalize raw shareholding data into standard format.
        
        Args:
            raw_data: Raw shareholding data from source
            
        Returns:
            Dict with period keys and normalized ShareholdingData values
        """
        normalized = {}
        
        for period, data in raw_data.items():
            if not self._is_valid_period(period):
                self.anomalies.append(ShareholdingAnomaly(
                    period=period,
                    issue="Invalid period format",
                    details=f"Period '{period}' is not in expected format (e.g., '2024-Q1' or 'Mar 2024')",
                    severity="error"
                ))
                continue
                
            normalized_data: ShareholdingData = {
                'promoter': 0.0,
                'fii': 0.0,
                'dii': 0.0,
                'public': 0.0,
                'government': 0.0,
                'other': 0.0
            }
            
            # Track total for validation
            total = 0.0
            valid_categories = 0
            
            for raw_category, value in data.items():
                # Clean and normalize category name
                category = self._normalize_category(raw_category)
                
                if not category:
                    self.anomalies.append(ShareholdingAnomaly(
                        period=period,
                        issue="Invalid shareholding category",
                        details=f"Category '{raw_category}' is not a recognized shareholding type",
                        severity="warning"
                    ))
                    continue
                
                # Ensure value is a valid percentage
                try:
                    value = float(value)
                    if value < 0 or value > 100:
                        raise ValueError("Percentage out of range")
                except (ValueError, TypeError):
                    self.anomalies.append(ShareholdingAnomaly(
                        period=period,
                        issue="Invalid percentage value",
                        details=f"Value '{value}' for category '{category}' is not a valid percentage",
                        severity="error"
                    ))
                    continue
                
                # Use current value if it exists (summing FII + DII)
                current = normalized_data.get(category) or 0.0
                normalized_data[category] = current + value
                total += value
                valid_categories += 1
            
            # Validate total is reasonable (allowing for small rounding differences)
            if valid_categories > 0 and not (99.5 <= total <= 100.5):
                self.anomalies.append(ShareholdingAnomaly(
                    period=period,
                    issue="Shareholding total out of expected range",
                    details=f"Sum of shareholding percentages is {total:.2f}% (expected ~100%)",
                    severity="error" if total > 100.5 or total < 99.5 else "warning"
                ))
            
            normalized[period] = normalized_data
        
        return normalized
    
    def _is_valid_period(self, period: str) -> bool:
        """Validate period format (e.g., '2024-Q1' or 'Mar 2024')"""
        try:
            # Check for YYYY-QQ format
            if '-' in period:
                year_part, qtr_part = period.split('-')
                if len(year_part) == 4 and year_part.isdigit() and \
                   qtr_part[0].upper() == 'Q' and qtr_part[1:].isdigit() and 1 <= int(qtr_part[1:]) <= 4:
                    return True
            
            # Check for MMM YYYY format
            try:
                datetime.strptime(period, '%b %Y')
                return True
            except ValueError:
                pass
                
            return False
        except:
            return False
    
    def _normalize_category(self, category: str) -> Optional[str]:
        """Convert various category names to standard format"""
        if not category:
            return None
            
        # Convert to lowercase and strip whitespace
        normalized = category.lower().strip()
        
        # Check if it's an allowed category
        if normalized in self.ALLOWED_CATEGORIES:
            return self.CATEGORY_MAPPING.get(normalized, normalized)
            
        # Check if it's a known variation
        for variant, standard in self.CATEGORY_MAPPING.items():
            if variant in normalized:
                return standard
                
        return None
    
    def get_anomalies(self) -> List[ShareholdingAnomaly]:
        """Get list of all detected anomalies"""
        return self.anomalies
    
    def has_errors(self) -> bool:
        """Check if any errors were found during validation"""
        return any(a.severity == "error" for a in self.anomalies)
    
    def get_shareholding_summary(self, normalized_data: Dict[str, ShareholdingData]) -> Dict:
        """
        Generate a summary of shareholding data for the latest period.
        
        Args:
            normalized_data: Output from normalize_shareholding_data()
            
        Returns:
            Dict with summary information
        """
        if not normalized_data:
            return {}
            
        # Get the most recent period
        latest_period = sorted(normalized_data.keys())[-1]
        latest_data = normalized_data[latest_period]
        
        # Calculate total for verification
        total = sum(v for v in latest_data.values() if v is not None)
        
        return {
            'period': latest_period,
            'data': latest_data,
            'total_percentage': round(total, 2),
            'is_valid': 99.5 <= total <= 100.5,
            'anomaly_count': len([a for a in self.anomalies if a.period == latest_period])
        }
