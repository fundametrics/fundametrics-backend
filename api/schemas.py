from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

# ─── Company Schemas ───────────────────────────────────────────────

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

class CompanyListRead(CompanyRead):
    market_cap: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    pe: Optional[Decimal] = None
    debt: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None

# ─── Fact / Metric Schemas ─────────────────────────────────────────

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
    type: str  # BOARD or EXECUTIVE
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

# ─── Phase 1: Live Data Schemas ────────────────────────────────────

class LiveDataResponse(BaseModel):
    """Response from yfinance live data endpoint."""
    symbol: str
    price: Optional[float] = None
    previous_close: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    volume: Optional[int] = None
    average_volume: Optional[int] = None
    fetched_at: str

# ─── Phase 2: Cache Status Schemas ─────────────────────────────────

class CacheStatusResponse(BaseModel):
    """Cache status for a symbol's fundamentals data."""
    symbol: str
    cache_status: str  # "fresh" | "stale_refreshing" | "stale" | "missing"
    status: Optional[str] = None # Backwards compatibility ("generating", "available", "not_found")
    message: Optional[str] = None
    cached_at: Optional[str] = None
    age_seconds: Optional[float] = None
    age_human: Optional[str] = None
    next_refresh_at: Optional[str] = None
    ttl_hours: float = 24.0
    live_price_age_seconds: Optional[float] = None

# ─── Phase 5: Sector Comparison Schemas ─────────────────────────────

class SectorStatItem(BaseModel):
    median: Optional[float] = None
    mean: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    best_symbol: Optional[str] = None
    best_value: Optional[float] = None
    worst_symbol: Optional[str] = None
    worst_value: Optional[float] = None
    sample_size: int = 0

class SectorSummaryResponse(BaseModel):
    sector_name: Optional[str] = None
    sector_stats: Dict[str, SectorStatItem] = {}
    symbols_count: int = 0
    computed_at: str = ""

class PeerComparisonResponse(BaseModel):
    subject: Dict[str, Any] = {}
    peers: List[Dict[str, Any]] = []
    percentile_ranks: Dict[str, Optional[float]] = {}
    sector_summary: Dict[str, Any] = {}
    computed_at: str = ""

# ─── Phase 6: Watchlist Schemas ─────────────────────────────────────

class WatchlistAdd(BaseModel):
    symbol: str
    notes: Optional[str] = None

class WatchlistUpdate(BaseModel):
    notes: Optional[str] = None

class WatchlistItem(BaseModel):
    symbol: str
    added_at: datetime
    notes: Optional[str] = None
    # Latest cached metrics (populated at query time)
    price: Optional[float] = None
    pe_ratio: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    change_1d: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)

class WatchlistResponse(BaseModel):
    user_id: str
    symbols: List[WatchlistItem] = []
    total: int = 0

# ─── Phase 7: Scheduler Schemas ─────────────────────────────────────

class SchedulerStatusResponse(BaseModel):
    started_at: Optional[str] = None
    is_running: bool = False
    last_runs: Dict[str, Any] = {}
    next_runs: Dict[str, Optional[str]] = {}
    failure_counts: Dict[str, int] = {}
    skipped_symbols: List[str] = []

# ─── Phase 8: Coverage / Quality Schemas ────────────────────────────

class CoverageBucket(BaseModel):
    range_label: str
    count: int
    symbols: List[str] = []

class CoverageResponse(BaseModel):
    total_symbols: int = 0
    distribution: List[CoverageBucket] = []
    lowest_completeness: List[Dict[str, Any]] = []
    anomaly_symbols: List[Dict[str, Any]] = []
