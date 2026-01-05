from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Integer, Numeric, Text, ForeignKey, Enum, Boolean, DateTime, Date, BigInteger, Index, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    symbol: Mapped[str] = mapped_column(String(50))
    exchange: Mapped[str] = mapped_column(Enum('NSE', 'BSE', 'BOTH'), default='NSE')
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    website_url: Mapped[Optional[str]] = mapped_column(String(255))
    about: Mapped[Optional[str]] = mapped_column(Text)
    summary_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    facts: Mapped[List["CompanyFact"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    financials: Mapped[List["FinancialYearly"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    metrics: Mapped[List["ComputedMetric"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    shareholding: Mapped[List["Shareholding"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    management: Mapped[List["Management"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_symbol_exchange", "symbol", "exchange", unique=True),
    )

class CompanyFact(Base):
    """Stores raw corporate constants and accounting facts"""
    __tablename__ = "company_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    face_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    book_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    shares_outstanding: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    snapshot_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="facts")

class ComputedMetric(Base):
    """Stores internal Fundametrics-computed analytics and ratios"""
    __tablename__ = "computed_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    metric_name: Mapped[str] = mapped_column(String(150))
    period: Mapped[date] = mapped_column(Date)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Phase 17A: Confidence
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    reason: Mapped[Optional[str]] = mapped_column(Text)

    # Phase 17B: Explainability
    explainability: Mapped[Optional[dict]] = mapped_column(JSON)
    integrity: Mapped[Optional[str]] = mapped_column(String(20)) # verified, partial, blocked

    # Phase 17C: Drift
    drift: Mapped[Optional[dict]] = mapped_column(JSON)

    # Phase 17D: Source Provenance
    source_provenance: Mapped[Optional[dict]] = mapped_column(JSON)
    
    # Phase 17E: Trust
    trust_score: Mapped[Optional[dict]] = mapped_column(JSON)

    company: Mapped["Company"] = relationship(back_populates="metrics")

class FinancialYearly(Base):
    __tablename__ = "financials_yearly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    # statement_type: Mapped[str] = mapped_column(Enum('P&L', 'BALANCE_SHEET', 'CASH_FLOW', 'QUARTERS'))
    statement_type: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(150))
    fiscal_year: Mapped[date] = mapped_column(Date)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Phase 17D: Source Provenance for raw facts
    source_provenance: Mapped[Optional[dict]] = mapped_column(JSON)

    company: Mapped["Company"] = relationship(back_populates="financials")

class Shareholding(Base):
    __tablename__ = "shareholding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(Enum('PROMOTER', 'FII', 'DII', 'PUBLIC', 'OTHERS'))
    quarter_date: Mapped[date] = mapped_column(Date)
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="shareholding")

class Management(Base):
    __tablename__ = "management"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    designation: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(Enum('BOARD', 'EXECUTIVE'), default='BOARD')
    experience: Mapped[Optional[str]] = mapped_column(Text)
    qualification: Mapped[Optional[str]] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="management")

class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Enum('SUCCESS', 'FAILED', 'PARTIAL'))
    message: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    items_scraped: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
