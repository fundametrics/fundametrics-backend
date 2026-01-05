import logging
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from db.models import Company, CompanyFact, ComputedMetric, FinancialYearly, Shareholding, Management, ScrapeLog

log = logging.getLogger(__name__)

class DataRepository:
    """
    Handles all database CRUD operations for stock data.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_company(self, symbol: str, name: str, **kwargs) -> Company:
        """
        Retrieves a company by symbol or creates it if it doesn't exist.
        """
        symbol = symbol.upper()
        stmt = select(Company).where(Company.symbol == symbol)
        result = await self.session.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            log.info(f"Creating new company: {symbol} - {name}")
            company = Company(symbol=symbol, name=name, **kwargs)
            self.session.add(company)
            await self.session.flush() # Get ID
        else:
            # Update metadata if changed
            changed = False
            for k, v in kwargs.items():
                if hasattr(company, k) and getattr(company, k) != v:
                    setattr(company, k, v)
                    changed = True
            if changed:
                await self.session.flush()

        return company

    async def save_company_facts(self, company_id: int, facts: Dict[str, Any]):
        """
        Saves a snapshot of raw corporate facts. 
        Always creates a new record for historical tracking.
        """
        f_data = {
            "company_id": company_id,
            "snapshot_date": date.today(),
            "face_value": facts.get("face_value"),
            "book_value": facts.get("book_value"),
            "shares_outstanding": facts.get("shares_outstanding")
        }

        fact_entry = CompanyFact(**f_data)
        self.session.add(fact_entry)
        await self.session.flush()

    async def save_computed_metric(self, company_id: int, metric_name: str, period: date, value: float):
        """
        Saves an internally computed Fundametrics metric.
        """
        metric = ComputedMetric(
            company_id=company_id,
            metric_name=metric_name,
            period=period,
            value=value
        )
        self.session.add(metric)
        await self.session.flush()

    async def save_financials_yearly(self, company_id: int, financials: Dict[str, Dict[str, Dict[str, Any]]]):
        """
        Saves yearly financial facts.
        Expects year-keyed format: financials[statement_type][year] = {metric: value}
        """
        statement_map = {
            'income_statement': 'P&L',
            'balance_sheet': 'BALANCE_SHEET',
            'cash_flow': 'CASH_FLOW',
            'quarters': 'QUARTERS'
        }

        for raw_stmt_type, years_data in financials.items():
            statement_type = statement_map.get(raw_stmt_type)
            if not statement_type:
                continue

            for period_str, metrics in years_data.items():
                try:
                    # Parse period (e.g., 'Mar 2023' or '2023')
                    import re
                    year_match = re.search(r'(\d{4})', period_str)
                    if not year_match:
                        continue
                    
                    year = int(year_match.group(1))
                    fiscal_date = date(year, 3, 31) # Standardized internal date

                    for metric_name, val in metrics.items():
                        if val is None:
                            continue

                        # Check if exists
                        stmt = select(FinancialYearly).where(
                            FinancialYearly.company_id == company_id,
                            FinancialYearly.statement_type == statement_type,
                            FinancialYearly.metric_name == metric_name,
                            FinancialYearly.fiscal_year == fiscal_date
                        )
                        result = await self.session.execute(stmt)
                        existing = result.scalar_one_or_none()
                        
                        if not existing:
                            fin = FinancialYearly(
                                company_id=company_id,
                                statement_type=statement_type,
                                metric_name=metric_name,
                                fiscal_year=fiscal_date,
                                value=val
                            )
                            self.session.add(fin)
                        else:
                            existing.value = val # Update if changed
                except Exception as e:
                    log.debug(f"Failed to save financial set for {period_str}: {e}")

    async def save_management(self, company_id: int, mgmt_data: List[Dict[str, Any]], mgmt_type: str = 'BOARD'):
        """
        Saves management details.
        """
        for person in mgmt_data:
            name = person.get("name")
            if not name:
                continue
            
            # Check if person already exists in management for this company
            stmt = select(Management).where(
                Management.company_id == company_id,
                Management.name == name,
                Management.type == mgmt_type
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if not existing:
                m = Management(
                    company_id=company_id,
                    name=name,
                    designation=person.get("designation"),
                    type=mgmt_type,
                    experience=person.get("experience"),
                    qualification=person.get("qualification")
                )
                self.session.add(m)
            else:
                # Update existing if needed
                existing.designation = person.get("designation")
                existing.experience = person.get("experience")
                existing.qualification = person.get("qualification")

    async def log_scrape(self, company_id: Optional[int], status: str, message: str = None, duration_ms: int = 0, items: int = 0):
        """
        Records a scrape attempt (Internal use only).
        """
        log_entry = ScrapeLog(
            company_id=company_id,
            status=status,
            message=message,
            duration_ms=duration_ms,
            items_scraped=items
        )
        self.session.add(log_entry)
        await self.session.commit()
