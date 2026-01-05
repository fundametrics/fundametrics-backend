import logging
from scraper.main import run_scraper

logger = logging.getLogger(__name__)

def scrape_symbol_job(symbol: str):
    """
    Scheduler job to scrape and persist data for a single symbol.
    This function should contain no business logic beyond orchestration.
    """
    try:
        logger.info(f"[Scheduler] Starting scrape for symbol: {symbol}")
        run_scraper(symbol)
        logger.info(f"[Scheduler] Completed scrape for symbol: {symbol}")
    except Exception as exc:
        logger.exception(
            f"[Scheduler] Scrape failed for symbol: {symbol} | Error: {exc}"
        )
        raise
