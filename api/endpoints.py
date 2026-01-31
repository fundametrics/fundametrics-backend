from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from db.manager import db_manager
from db.models import Company, CompanyFact, ComputedMetric, FinancialYearly, Management, ScrapeLog
from api.schemas import CompanyRead, FactRead, MetricRead, FundametricsMetricRead, FinancialMetric, ManagementRead, StockDetailRead, ScrapeLogRead

router = APIRouter()

async def get_db() -> AsyncSession:
    if db_manager is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    async with db_manager.session_factory() as session:
        yield session

@router.get("/stocks", response_model=List[CompanyRead])
async def list_stocks(
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    sector: Optional[str] = None,
    min_market_cap: Optional[float] = None,
    max_market_cap: Optional[float] = None,
    min_roe: Optional[float] = None,
    max_pe: Optional[float] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all companies with filters.
    """
    from sqlalchemy.orm import aliased
    from sqlalchemy import and_, or_

    stmt = select(Company)

    # 1. Basic Search
    if search:
        stmt = stmt.where(
            (Company.name.ilike(f"%{search}%")) | (Company.symbol.ilike(f"%{search}%"))
        )
    
    # 2. Section Filter
    if sector and sector != 'all':
        stmt = stmt.where(Company.sector == sector)

    # 3. Numeric Filters (Using EXISTs/JOINs for filtering)
    # We join with specific metric rows if filtering is requested
    
    if min_market_cap is not None:
        mc_alias = aliased(ComputedMetric)
        stmt = stmt.join(mc_alias, and_(
            Company.id == mc_alias.company_id,
            mc_alias.metric_name.in_(['Market Cap', 'Market Capitalization']),
            mc_alias.value >= min_market_cap
        ))

    if max_market_cap is not None:
        mc_alias_max = aliased(ComputedMetric)
        stmt = stmt.join(mc_alias_max, and_(
            Company.id == mc_alias_max.company_id,
            mc_alias_max.metric_name.in_(['Market Cap', 'Market Capitalization']),
            mc_alias_max.value <= max_market_cap
        ))

    if min_roe is not None:
        roe_alias = aliased(ComputedMetric)
        stmt = stmt.join(roe_alias, and_(
            Company.id == roe_alias.company_id,
            roe_alias.metric_name.in_(['ROE', 'Return on Equity']),
            roe_alias.value >= min_roe
        ))
        
    if max_pe is not None:
        pe_alias = aliased(ComputedMetric)
        stmt = stmt.join(pe_alias, and_(
            Company.id == pe_alias.company_id,
            pe_alias.metric_name.in_(['P/E Ratio', 'PE Ratio']),
            pe_alias.value <= max_pe
        ))

    # Apply Pagination
    stmt = stmt.offset(skip).limit(limit)
    
    # Execute Base Query
    result = await db.execute(stmt)
    companies = result.scalars().all()

    # 4. Hydrate Metrics (Efficient ID-based fetch)
    # Since we need to return values (even if not filtering by them), we fetch them for the result set
    if companies:
        company_ids = [c.id for c in companies]
        
        # Fetch relevant metrics for these companies
        metrics_stmt = select(ComputedMetric).where(
            ComputedMetric.company_id.in_(company_ids),
            ComputedMetric.metric_name.in_([
                'Market Cap', 'Market Capitalization', 
                'ROE', 'Return on Equity', 
                'P/E Ratio', 'PE Ratio',
                'Debt to Equity', 'Debt',
                '1Y Return'
            ])
        ).order_by(desc(ComputedMetric.period)) # Prefer latest
        
        m_result = await db.execute(metrics_stmt)
        all_metrics = m_result.scalars().all()
        
        # Map metrics to companies
        # Use a dictionary for fast lookup: {company_id: {metric_name: value}}
        metrics_map = {}
        for m in all_metrics:
            if m.company_id not in metrics_map:
                metrics_map[m.company_id] = {}
            
            # Since we ordered by period desc, the first time we see a metric name, it's the latest
            name = m.metric_name
            normalized_name = 'market_cap' if name in ['Market Cap', 'Market Capitalization'] else \
                              'roe' if name in ['ROE', 'Return on Equity'] else \
                              'pe' if name in ['P/E Ratio', 'PE Ratio'] else \
                              'debt' if name in ['Debt', 'Debt to Equity'] else \
                              'change_percent' if name == '1Y Return' else None
            
            if normalized_name and normalized_name not in metrics_map[m.company_id]:
                 metrics_map[m.company_id][normalized_name] = m.value

        # Construct Response Objects
        final_results = []
        for c in companies:
            c_dict = c.__dict__
            # Add metric values from map
            c_metrics = metrics_map.get(c.id, {})
            
            # Create a combined object (schema validation will handle the rest if we match fields)
            # We use dynamic object creation to match CompanyListRead
            c.market_cap = c_metrics.get('market_cap')
            c.roe = c_metrics.get('roe')
            c.pe = c_metrics.get('pe')
            c.debt = c_metrics.get('debt')
            c.change_percent = c_metrics.get('change_percent')
            final_results.append(c)
            
        return final_results
    
    return []

@router.get("/stocks/{symbol}", response_model=StockDetailRead)
async def get_stock_detail(symbol: str, db: AsyncSession = Depends(get_db)):
    """
    Get comprehensive fundamental data for a specific stock by symbol.
    Returns neutral raw facts and internally computed Fundametrics proprietary metrics.
    """
    symbol = symbol.upper()
    
    # 1. Fetch Company
    stmt = select(Company).where(Company.symbol == symbol)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    
    if not company:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
    
    # 2. Latest Facts
    f_stmt = select(CompanyFact).where(CompanyFact.company_id == company.id).order_by(desc(CompanyFact.snapshot_date)).limit(1)
    f_result = await db.execute(f_stmt)
    latest_f = f_result.scalar_one_or_none()
    
    # 3. Historical Facts (last 5 snapshots)
    h_stmt = select(CompanyFact).where(CompanyFact.company_id == company.id).order_by(desc(CompanyFact.snapshot_date)).offset(1).limit(5)
    h_result = await db.execute(h_stmt)
    history_f = h_result.scalars().all()
    
    # 4. Computed Metrics
    m_stmt = select(ComputedMetric).where(ComputedMetric.company_id == company.id).order_by(desc(ComputedMetric.period))
    m_result = await db.execute(m_stmt)
    metrics = m_result.scalars().all()

    # 5. Yearly Financials
    fin_stmt = select(FinancialYearly).where(FinancialYearly.company_id == company.id).order_by(desc(FinancialYearly.fiscal_year))
    fin_result = await db.execute(fin_stmt)
    financials = fin_result.scalars().all()
    
    # Group financials by statement type
    grouped_financials = {}
    for fin in financials:
        s_type = fin.statement_type
        if s_type not in grouped_financials:
            grouped_financials[s_type] = []
        grouped_financials[s_type].append(fin)
    
    # 5. Management
    m_stmt = select(Management).where(Management.company_id == company.id)
    m_result = await db.execute(m_stmt)
    mgmt = m_result.scalars().all()
    
    return {
        "company": company,
        "latest_facts": latest_f,
        "historical_facts": history_f,
        "fundametrics_metrics": metrics,
        "yearly_financials": grouped_financials,
        "management": mgmt
    }

@router.get("/logs", response_model=List[ScrapeLogRead])
async def get_scrape_logs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """
    Get recent scrape logs for monitoring.
    """
    stmt = select(ScrapeLog).order_by(desc(ScrapeLog.created_at)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

from pydantic import BaseModel
class CompareRequest(BaseModel):
    metric_a: Dict[str, Any]
    metric_b: Dict[str, Any]

@router.post("/compare/check")
async def check_comparison_eligibility(payload: CompareRequest):
    """
    Phase 18B: Validates if two metrics can be compared safely.
    """
    from scraper.core.compare import can_compare
    result = can_compare(payload.metric_a, payload.metric_b)
    return result
