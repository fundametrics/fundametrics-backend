"""
Initialize the database and populate it with scraped stock data
"""
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from db.models import Base, Company, CompanyFact, FinancialYearly, Shareholding, Management, ScrapeLog

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env file")

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_database():
    """Create all tables"""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully!")


async def load_scraped_data():
    """Load data from JSON files in the data directory"""
    data_dir = Path("data")
    if not data_dir.exists():
        print("⚠️  No data directory found. Skipping data import.")
        return
    
    json_files = list(data_dir.glob("*.json"))
    if not json_files:
        print("⚠️  No JSON files found in data directory. Skipping data import.")
        return
    
    print(f"\n📂 Found {len(json_files)} JSON files to import...")
    
    async with SessionLocal() as session:
        for json_file in json_files:
            try:
                print(f"\n📄 Processing {json_file.name}...")
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract company info
                symbol = data.get('symbol', '').upper()
                if not symbol:
                    print(f"  ⚠️  No symbol found in {json_file.name}, skipping...")
                    continue
                
                # Check if company already exists
                stmt = select(Company).where(Company.symbol == symbol)
                result = await session.execute(stmt)
                company = result.scalar_one_or_none()
                
                if company:
                    print(f"  ℹ️  Company {symbol} already exists, updating...")
                else:
                    # Create new company
                    company = Company(
                        symbol=symbol,
                        name=data.get('company_name', f"{symbol} Limited"),
                        exchange='NSE',
                        sector=data.get('sector', 'Not disclosed'),
                        industry=data.get('industry', 'Not disclosed'),
                        website_url=data.get('website_url'),
                        about=data.get('about'),
                        is_active=True
                    )
                    session.add(company)
                    await session.flush()  # Get the company ID
                    print(f"  ✅ Created company: {symbol}")
                
                # Add company facts if available
                if 'face_value' in data or 'book_value' in data:
                    fact = CompanyFact(
                        company_id=company.id,
                        face_value=Decimal(str(data.get('face_value', 0))) if data.get('face_value') else None,
                        book_value=Decimal(str(data.get('book_value', 0))) if data.get('book_value') else None,
                        shares_outstanding=Decimal(str(data.get('shares_outstanding', 0))) if data.get('shares_outstanding') else None,
                        snapshot_date=date.today()
                    )
                    session.add(fact)
                    print(f"  ✅ Added company facts")
                
                # Add financial data if available
                for statement_type in ['quarterly_results', 'profit_loss', 'balance_sheet', 'cash_flow']:
                    if statement_type in data and data[statement_type]:
                        financial_data = data[statement_type]
                        if isinstance(financial_data, dict):
                            for metric_name, value in financial_data.items():
                                if isinstance(value, (int, float, str)):
                                    try:
                                        financial = FinancialYearly(
                                            company_id=company.id,
                                            statement_type=statement_type.upper().replace('_', ' '),
                                            metric_name=metric_name,
                                            fiscal_year=date.today(),
                                            value=Decimal(str(value)) if value else None,
                                            source_provenance={
                                                "source": "scraped_json",
                                                "file": str(json_file.name),
                                                "scraped_at": datetime.utcnow().isoformat(),
                                                "statement": statement_type,
                                                "metric": metric_name
                                            }
                                        )
                                        session.add(financial)
                                    except:
                                        pass
                        print(f"  ✅ Added {statement_type} data")
                
                # Add shareholding data if available
                if 'shareholding' in data and isinstance(data['shareholding'], dict):
                    for category, percentage in data['shareholding'].items():
                        if isinstance(percentage, (int, float)):
                            shareholding = Shareholding(
                                company_id=company.id,
                                category=category.upper(),
                                quarter_date=date.today(),
                                percentage=Decimal(str(percentage))
                            )
                            session.add(shareholding)
                    print(f"  ✅ Added shareholding data")
                
                # Log the scrape
                log = ScrapeLog(
                    company_id=company.id,
                    status='SUCCESS',
                    message=f"Imported from {json_file.name}",
                    items_scraped=1,
                    created_at=datetime.utcnow()
                )
                session.add(log)
                
                await session.commit()
                print(f"  ✅ Successfully imported {symbol} from {json_file.name}")
                
            except Exception as e:
                print(f"  ❌ Error processing {json_file.name}: {e}")
                await session.rollback()
                continue
    
    print("\n✅ Data import completed!")


async def main():
    print("=" * 60)
    print("FUNDAMETRICS DATABASE INITIALIZATION")
    print("=" * 60)
    
    await init_database()
    await load_scraped_data()
    
    print("\n" + "=" * 60)
    print("✅ Database setup complete!")
    print("=" * 60)
    print("\nYou can now start the API server with:")
    print("  python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    asyncio.run(main())
