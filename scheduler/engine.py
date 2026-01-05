import asyncio
import time
from datetime import date
from typing import List, Dict, Any, Optional
from scraper.core.fetcher import Fetcher
from scraper.sources.screener import ScreenerScraper as FinancialScraper
from scraper.sources.trendlyne import TrendlyneScraper as ProfileScraper
from scraper.utils.pipeline import DataPipeline
from scraper.utils.logger import get_logger
from db.manager import db_manager
from db.repository import DataRepository

log = get_logger(__name__)

class ScraperEngine:
    """
    Coordinates the multi-source scraping process, data cleaning,
    validation, and database storage.
    """

    def __init__(self, fetcher: Optional[Fetcher] = None, max_concurrency: int = 5):
        self.fetcher = fetcher or Fetcher()
        self.financial_scraper = FinancialScraper(self.fetcher)
        self.profile_scraper = ProfileScraper(self.fetcher)
        self.pipeline = DataPipeline()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        
        # Source control (could be moved to a config object)
        self.sources_config = {
            "external_source_1": True,
            "external_source_2": True
        }

    async def scrape_single_symbol(self, symbol: str) -> bool:
        """
        Executes end-to-end scrape for one symbol.
        Returns True if successful.
        """
        start_time = time.time()
        symbol = symbol.upper()
        log.info(f"--- Starting Scrape Session for {symbol} ---")
        
        async with db_manager.session_factory() as session:
            repo = DataRepository(session)
            company_id = None
            
            try:
                # 1. Fetch from External Financial Data Source
                financial_data = {}
                if self.sources_config.get("external_source_1", True):
                    financial_data = await self.financial_scraper.scrape_stock(symbol)
                
                if not financial_data and self.sources_config.get("external_source_1"):
                    await repo.log_scrape(None, "External Source 1", "FAILED", f"No data found for {symbol}", duration_ms=int((time.time()-start_time)*1000))
                    return False

                # 2. Fetch from External Profile Source
                profile_data = {}
                if self.sources_config.get("external_source_2", True):
                    profile_data = await self.profile_scraper.scrape_stock(symbol)
                
                # 3. Consolidate Raw Data
                raw_data = {
                    "symbol": symbol,
                    "company_name": financial_data.get("company_name") or profile_data.get("company_name", symbol),
                    "website_url": financial_data.get("website_url"),
                    "ratios": financial_data.get("ratios", {}),
                    "financial_tables": financial_data.get("financial_tables", {}),
                    "shareholding_pattern": financial_data.get("shareholding_pattern", {}),
                    "sector": profile_data.get("sector"),
                    "industry": profile_data.get("industry"),
                    "about": profile_data.get("about"),
                    "management": profile_data.get("management", []),
                    "executives": profile_data.get("executives", [])
                }

                # 4. Pipeline (Clean & Validate)
                processed = self.pipeline.process_stock_data(raw_data)
                cleaned = processed["cleaned_data"]
                report = processed["validation_report"]

                if not report["is_valid"]:
                    log.warning(f"Validation failed for {symbol}: {report['errors']}")
                    # We still proceed but log as PARTIAL/WARNING? Or block?
                    # For now, let's proceed to save but log errors.

                # 5. Database Save
                # a. Get/Create Company
                company = await repo.get_or_create_company(
                    symbol=symbol,
                    name=cleaned.get("company_name", "Unknown"),
                    sector=cleaned.get("sector"),
                    industry=cleaned.get("industry"),
                    website_url=cleaned.get("website_url"),
                    about=cleaned.get("about")
                )
                company_id = company.id

                # b. Save Fundamentals
                await repo.save_fundamentals(company_id, cleaned.get("ratios", {}), "external_source_1")

                # c. Save Financials
                await repo.save_financials_yearly(company_id, cleaned.get("financial_tables", {}))

                # d. Save Management
                if cleaned.get("management"):
                    await repo.save_management(company_id, cleaned.get("management"), 'BOARD')
                if cleaned.get("executives"):
                    await repo.save_management(company_id, cleaned.get("executives"), 'EXECUTIVE')

                # e. Log success
                duration = int((time.time() - start_time) * 1000)
                await repo.log_scrape(company_id, "ALL", "SUCCESS", duration_ms=duration, items=1)
                
                await session.commit()
                log.info(f"--- Completed Scrape Session for {symbol} in {duration/1000:.2f}s ---")
                return True

            except Exception as e:
                log.exception(f"Unexpected error in scrape session for {symbol}: {e}")
                duration = int((time.time() - start_time) * 1000)
                await repo.log_scrape(company_id, "ALL", "FAILED", message=str(e), duration_ms=duration)
                return False

    async def run_bulk_scrape(self, symbols: List[str]):
        """
        Runs scrape for a list of symbols in parallel using a semaphore.
        """
        log.info(f"Starting bulk scrape for {len(symbols)} symbols with max_concurrency={self.semaphore._value}")
        
        async def bounded_scrape(symbol):
            async with self.semaphore:
                # Add a small random jitter before starting each to spread the load further
                import random
                await asyncio.sleep(random.uniform(1, 5)) 
                return await self.scrape_single_symbol(symbol)

        tasks = [bounded_scrape(s) for s in symbols]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r)
        log.info(f"Bulk scrape completed. Success: {success_count}/{len(symbols)}")
