from typing import List, Dict, Any
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from scraper.core.fetcher import Fetcher
from scraper.utils.logger import get_logger

log = get_logger(__name__)

class NewsScraper:
    """
    Scraper for stock-related news using Google News RSS.
    """
    
    BASE_URL = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher

    async def fetch_news(self, symbol: str, company_name: str = "") -> List[Dict[str, Any]]:
        """
        Fetches latest news for a given symbol.
        """
        query = f"{symbol}"
        if company_name and company_name != symbol:
            query = f"{company_name} {symbol}"
        
        url = self.BASE_URL.format(query=query.replace(" ", "+") + "+stock+news")
        log.info(f"Fetching news for {symbol} from {url}")
        
        try:
            xml_text = await self.fetcher.fetch_html(url)
            if not xml_text:
                return []
            
            root = ET.fromstring(xml_text)
            news_items = []
            
            for item in root.findall(".//item")[:10]: # Top 10 news
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                source = item.find("source").text if item.find("source") is not None else "Unknown"
                
                # Cleanup title (Google News appends " - Source Name")
                clean_title = title
                if " - " in title:
                    clean_title = " - ".join(title.split(" - ")[:-1])
                
                news_items.append({
                    "title": clean_title,
                    "url": link,
                    "published_at": pub_date,
                    "source": source,
                    "sentiment": self._simple_sentiment(clean_title)
                })
                
            return news_items
            
        except Exception as e:
            log.error(f"Error fetching news for {symbol}: {e}")
            return []

    def _simple_sentiment(self, text: str) -> str:
        """
        Extremely basic rule-based sentiment detection for news titles.
        """
        text = text.lower()
        positive = ["buy", "gain", "surge", "growth", "profit", "bull", "jump", "positive", "high", "upgrade", "outperform"]
        negative = ["sell", "loss", "fall", "dip", "bear", "plunge", "negative", "low", "downgrade", "underperform", "crash"]
        
        pos_count = sum(1 for word in positive if word in text)
        neg_count = sum(1 for word in negative if word in text)
        
        if pos_count > neg_count: return "positive"
        if neg_count > pos_count: return "negative"
        return "neutral"
