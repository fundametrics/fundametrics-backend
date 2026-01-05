import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scheduler.engine import ScraperEngine
from scraper.utils.logger import setup_logging

async def test_engine_dry_run():
    setup_logging()
    
    # Mock symbols and dependencies
    symbols = ["RELIANCE"]
    
    # We need to mock db_manager to avoid connection errors
    import scheduler.engine
    scheduler.engine.db_manager = MagicMock()
    # Mock session factory context manager
    mock_session = AsyncMock()
    scheduler.engine.db_manager.session_factory.return_value.__aenter__.return_value = mock_session
    
    # Mock DataRepository
    mock_repo_class = MagicMock()
    scheduler.engine.DataRepository = mock_repo_class
    mock_repo = mock_repo_class.return_value
    mock_repo.log_scrape = AsyncMock()
    mock_repo.get_or_create_company = AsyncMock(return_value=MagicMock(id=1))
    mock_repo.save_fundamentals = AsyncMock()
    mock_repo.save_financials_yearly = AsyncMock()
    mock_repo.save_management = AsyncMock()
    
    engine = ScraperEngine()
    
    print("Starting Dry Run...")
    success = await engine.scrape_single_symbol("RELIANCE")
    
    print(f"Dry Run Finished. Success: {success}")
    
    # Verify repo calls
    if success:
        print("Verifying repository calls...")
        mock_repo.get_or_create_company.assert_called()
        mock_repo.save_fundamentals.assert_called()
        print("Verified!")

if __name__ == "__main__":
    asyncio.run(test_engine_dry_run())
