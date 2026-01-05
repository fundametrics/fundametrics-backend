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
    db: AsyncSession = Depends(get_db)
):
    """
    List all companies. Supports search by name or symbol.
    """
    stmt = select(Company)
    if search:
        stmt = stmt.where(
            (Company.name.ilike(f"%{search}%")) | (Company.symbol.ilike(f"%{search}%"))
        )
    
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

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
