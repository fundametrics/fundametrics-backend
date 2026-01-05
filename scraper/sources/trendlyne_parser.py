import json
import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class TrendlyneParser:
    """
    Parser for external profile HTML content.
    Handles extraction of sector, history, and management snapshots.
    """

    def __init__(self, html: str, symbol: Optional[str] = None):
        self.soup = BeautifulSoup(html, 'lxml')
        self.symbol = symbol

    def _summarize_text(self, text: str) -> str:
        """Basic summarization to avoid verbatim storage of third-party text"""
        if not text:
            return ""
        # Split into sentences, keep only the first 3-4 for a summary
        sentences = re.split(r'(?<=[.!?])\s+', text)
        summary = " ".join(sentences[:4]).strip()
        # Clean up any lingering source names
        summary = re.sub(r'moneycontrol|screener|trendlyne', 'Fundametrics', summary, flags=re.I)
        return summary

    def extract_sector_industry(self) -> Dict[str, Optional[str]]:
        """
        Extracts Sector and Industry from the main stock page.
        Usually found in breadcrumbs: SECTOR : XXX, INDUSTRY : YYY
        """
        data = {"sector": None, "industry": None}
        
        # Look for breadcrumb spans with property="name"
        spans = self.soup.find_all("span", {"property": "name"})
        for span in spans:
            text = span.get_text(strip=True).upper()
            if "SECTOR :" in text:
                data["sector"] = text.replace("SECTOR :", "").strip()
            elif "INDUSTRY :" in text:
                data["industry"] = text.replace("INDUSTRY :", "").strip()
        
        return data

    def extract_about_url(self) -> Optional[str]:
        """
        Extracts the URL for the 'About' page from the main page.
        Usually a link with data-modal-trigger and containing 'about' in href.
        """
        about_link = self.soup.find("a", href=re.compile(r'/equity/about/'))
        if about_link:
            url = about_link['href']
            if not url.startswith("http"):
                url = "https://trendlyne.com" + url
            return url
        return None

    def extract_profile_and_mgmt(self) -> Dict[str, Any]:
        """
        Extracts full profile and management data from the 'About' page.
        Uses JSON strings embedded in 'div#about-the-company' data attributes.
        """
        data = {
            "about": None,
            "history": None,
            "management": [],
            "executives": []
        }
        
        container = self.soup.find("div", id="about-the-company")
        if not container:
            logger.warning("Could not find div#about-the-company on Trendlyne About page.")
            return data

        # 1. Profile/About
        try:
            profile_json = container.get("data-get_business_profile")
            if profile_json:
                profile_data = json.loads(profile_json)
                raw_about = profile_data.get("profile")
                if raw_about:
                    data["about"] = self._summarize_text(raw_about)
                    data["summary_generated"] = True
        except Exception as e:
            logger.error(f"Error parsing Trendlyne business profile JSON: {e}")

        # 2. History (biodata)
        try:
            biodata_json = container.get("data-biodata")
            if biodata_json:
                biodata = json.loads(biodata_json)
                raw_history = biodata.get("biodata")
                if raw_history:
                    data["history"] = self._summarize_text(raw_history)
        except Exception as e:
            logger.error(f"Error parsing Trendlyne biodata JSON: {e}")

        # 3. Executives (Top Management)
        try:
            exec_json = container.get("data-get_top_executive")
            if exec_json:
                exec_list = json.loads(exec_json)
                for item in exec_list:
                    data["executives"].append({
                        "name": item.get("name"),
                        "designation": item.get("designation"),
                        "qualification": item.get("qualification"),
                        "experience": item.get("experience")
                    })
        except Exception as e:
            logger.error(f"Error parsing Trendlyne executives JSON: {e}")

        # 4. Directors
        try:
            dir_json = container.get("data-get_director_details")
            if dir_json:
                dir_list = json.loads(dir_json)
                for item in dir_list:
                    data["management"].append({
                        "name": item.get("name"),
                        "designation": item.get("designation"),
                        "qualification": item.get("qualification"),
                        "experience": item.get("experience")
                    })
        except Exception as e:
            logger.error(f"Error parsing Trendlyne directors JSON: {e}")

        return data

    def parse_all_info(self) -> Dict[str, Any]:
        """
        Helper method to return standardized info.
        """
        sector_industry = self.extract_sector_industry()
        profile_mgmt = self.extract_profile_and_mgmt()
        
        info = {
            "metadata": {
                "sector": sector_industry.get("sector"),
                "industry": sector_industry.get("industry")
            },
            "profile": {
                "description": profile_mgmt.get("about"),
                "history": profile_mgmt.get("history"),
                "summary_generated": profile_mgmt.get("summary_generated", False)
            },
            "management": profile_mgmt.get("management", []),
            "executives": profile_mgmt.get("executives", [])
        }
        return info
