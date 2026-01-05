from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict
from pydantic import BaseModel, ConfigDict

class CompanyBase(BaseModel):
    name: str
    symbol: str
    exchange: str
    sector: Optional[str] = None
    industry: Optional[str] = None

class CompanyRead(CompanyBase):
    id: int
    about: Optional[str] = None
    summary_generated: bool
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class FactRead(BaseModel):
    face_value: Optional[Decimal] = None
    book_value: Optional[Decimal] = None
    shares_outstanding: Optional[Decimal] = None
    snapshot_date: date
    
    model_config = ConfigDict(from_attributes=True)

class MetricRead(BaseModel):
    metric_name: str
    period: date
    value: Optional[Decimal] = None
    computed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class FundametricsMetricRead(BaseModel):
    """Fundametrics proprietary metrics computed internally from raw facts"""
    metric_name: str
    period: date
    value: Optional[Decimal] = None
    computed_at: datetime
    
    # Phase 17 Fields
    unit: Optional[str] = None
    confidence: Optional[Decimal] = None
    reason: Optional[str] = None
    explainability: Optional[Dict] = None
    drift: Optional[Dict] = None
    source_provenance: Optional[Dict] = None
    integrity: Optional[str] = None
    trust_score: Optional[Dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class FinancialMetric(BaseModel):
    metric_name: str
    fiscal_year: date
    value: Optional[Decimal] = None
    source_provenance: Optional[Dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class ManagementRead(BaseModel):
    name: str
    designation: Optional[str] = None
    type: str # BOARD or EXECUTIVE
    experience: Optional[str] = None
    qualification: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class StockDetailRead(BaseModel):
    company: CompanyRead
    latest_facts: Optional[FactRead] = None
    historical_facts: List[FactRead] = []
    yearly_financials: Dict[str, List[FinancialMetric]] = {}
    fundametrics_metrics: List[FundametricsMetricRead] = []
    management: List[ManagementRead] = []
    
    model_config = ConfigDict(from_attributes=True)

class ScrapeLogRead(BaseModel):
    id: int
    status: str
    message: Optional[str] = None
    duration_ms: Optional[int] = None
    items_scraped: Optional[int] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
