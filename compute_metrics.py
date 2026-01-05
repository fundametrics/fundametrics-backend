import asyncio
import os
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from db.models import Base, Company, FinancialYearly, ComputedMetric
from dotenv import load_dotenv
from scraper.core.engine import MetricEngine

load_dotenv()

# Force using the file in current dir
DATABASE_URL = "sqlite+aiosqlite:///./fundametrics_stock_data.db"
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def seed_and_compute():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with SessionLocal() as session:
            # 1. Ensure Company
            result = await session.execute(select(Company).where(Company.symbol == "ONGC"))
            company = result.scalar_one_or_none()
            if not company:
                print("Seeding ONGC...")
                company = Company(symbol="ONGC", name="Oil and Natural Gas Corporation", exchange="NSE", is_active=True)
                session.add(company)
                await session.commit()
                await session.refresh(company)
            
            print(f"Working on {company.symbol} (ID: {company.id})")

            # 2. Ensure Financials (Raw Facts)
            fy24 = date(2024, 3, 31)
            
            async def ensure_financial(metric, val):
                # print(f"Ensuring {metric}...")
                stmt = select(FinancialYearly).where(
                    FinancialYearly.company_id == company.id,
                    FinancialYearly.metric_name == metric,
                    FinancialYearly.fiscal_year == fy24
                )
                res = await session.execute(stmt)
                obj = res.scalar_one_or_none()
                if not obj:
                    print(f"Creating {metric}...")
                    obj = FinancialYearly(
                        company_id=company.id,
                        statement_type="P&L",
                        metric_name=metric,
                        fiscal_year=fy24,
                        value=Decimal(str(val)),
                        source_provenance={
                            "source": "NSE",
                            "filing_type": "Annual",
                            "statement_scope": "Consolidated",
                            "period": "FY24",
                            "scraped_at": datetime.utcnow().isoformat(),
                            "source_url": "https://nsearchives.nseindia.com/corporate/ONGC_31032024.pdf"
                        }
                    )
                    session.add(obj)
                return obj

            rev = await ensure_financial("Revenue", 138402.00) # Crores
            op_profit = await ensure_financial("Operating Profit", 76356.00)
            
            await session.commit()
            print("Financials ensured.")

            # 3. Compute Phase 17 Metrics via Engine
            print("Computing Fundametrics Operating Margin...")
            
            metric_engine = MetricEngine()
            
            # Logic
            if rev.value and op_profit.value:
                # Calculate raw value
                margin = float(op_profit.value / rev.value) * 100
                
                # Fetch history for Drift (Phase 17C)
                stmt_hist = select(ComputedMetric.value).where(
                    ComputedMetric.company_id == company.id,
                    ComputedMetric.metric_name == "Fundametrics Operating Margin",
                    ComputedMetric.period < fy24
                ).order_by(ComputedMetric.period.desc()).limit(5)
                res_hist = await session.execute(stmt_hist)
                history = [float(h) for h in res_hist.scalars().all()]
                
                # Prepare inputs for 17B/D
                inputs = [
                    {"name": "Revenue", "value": float(rev.value), "source": rev.source_provenance},
                    {"name": "Operating Profit", "value": float(op_profit.value), "source": op_profit.source_provenance}
                ]
                
                # Execute Engine
                metric_data = metric_engine.compute_metric(
                    metric_name="Fundametrics Operating Margin",
                    value=margin,
                    inputs=inputs,
                    formula="(Operating Profit / Revenue) * 100",
                    historical_values=history,
                    assumptions=["Consolidated figures used", "Standard formula"]
                )
                
                # Save ComputedMetric
                metric_name = "Fundametrics Operating Margin"
                stmt = select(ComputedMetric).where(
                    ComputedMetric.company_id == company.id,
                    ComputedMetric.metric_name == metric_name,
                    ComputedMetric.period == fy24
                )
                res = await session.execute(stmt)
                cm = res.scalar_one_or_none()
                
                if cm:
                    # Update existing
                    cm.value = metric_data['value']
                    cm.unit = metric_data['unit']
                    cm.confidence = metric_data['confidence']
                    cm.reason = metric_data['reason']
                    cm.explainability = metric_data['explainability']
                    cm.drift = metric_data['drift']
                    cm.source_provenance = metric_data['source_provenance']
                    cm.trust_score = metric_data['trust_score']
                    cm.integrity = metric_data['integrity']
                else:
                    # Create new
                    cm = ComputedMetric(
                        company_id=company.id,
                        metric_name=metric_name,
                        period=fy24,
                        **metric_data
                    )
                    session.add(cm)
                
                print(f"✅ Computed {metric_name}: {margin:.2f}%")
                print(f"  Trust Score: {metric_data['trust_score']['score']} ({metric_data['trust_score']['grade']})")
                print(f"  Drift: {metric_data['drift']['drift_flag']} (Z={metric_data['drift']['z_score']})")
            
            await session.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        with open("error_compute.log", "w") as f:
            traceback.print_exc(file=f)


if __name__ == "__main__":
    asyncio.run(seed_and_compute())
