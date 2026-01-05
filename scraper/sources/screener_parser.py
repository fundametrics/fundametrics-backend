"""
Fundamentals Parser - HTML Data Extraction
==========================================

Resilient parser for external fundamentals pages using BeautifulSoup.
Extracts:
- Company Information
- Raw constants
- Financial Tables (Quarters, P&L, Balance Sheet, Cash Flow)
- Shareholding Pattern
"""

from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
import re
from scraper.utils.logger import get_logger

log = get_logger(__name__)


class ScreenerParser:
    """
    Parser for external fundamental HTML pages.
    Refactored for Fundametrics: Extracts only raw numeric facts.
    """
    
    # Mapping of raw labels to neutral Fundametrics identifiers
    METRIC_MAP = {
        # Income Statement
        "Sales": "revenue",
        "Revenue": "revenue",
        "Revenue from Operations": "revenue",
        "Total Revenue": "revenue",
        "Net Sales": "revenue",
        "Operating Revenue": "revenue",
        "Expenses": "expenses",
        "Operating Profit": "operating_profit",
        "OPM %": "operating_profit_margin",
        "Other Income": "other_income",
        "Other Income +": "other_income",
        "Interest": "interest",
        "Depreciation": "depreciation",
        "Profit before tax": "profit_before_tax",
        "Tax %": "tax_pct",
        "Net Profit": "net_income",
        "Net Profit After Tax": "net_income",
        "Profit After Tax": "net_income",
        "PAT": "net_income",
        "Net Income": "net_income",
        "EPS in Rs": "eps",
        "Dividend Payout %": "dividend_payout_pct",
        
        # Balance Sheet
        "Equity Capital": "equity_capital",
        "Reserves": "reserves",
        "Borrowings": "borrowings",
        "Borrowings +": "borrowings",
        "Other Liabilities": "other_liabilities",
        "Other Liabilities +": "other_liabilities",
        "Total Liabilities": "total_liabilities",
        "Fixed Assets": "fixed_assets",
        "Fixed Assets +": "fixed_assets",
        "CWIP": "cwip",
        "Investments": "investments",
        "Other Assets": "other_assets",
        "Other Assets +": "other_assets",
        "Total Assets": "total_assets",
        
        # Cash Flow
        "Cash from Operating Activity": "cash_flow_operating",
        "Cash from Operating Activity +": "cash_flow_operating",
        "Cash from Investing Activity": "cash_flow_investing",
        "Cash from Investing Activity +": "cash_flow_investing",
        "Cash from Financing Activity": "cash_flow_financing",
        "Cash from Financing Activity +": "cash_flow_financing",
        "Net Cash Flow": "net_cash_flow",
        
        # Ratios (Raw Constants & Table)
        "Market Cap": "market_cap",
        "Current Price": "share_price",
        "Face Value": "face_value",
        "Book Value": "book_value",
        "Stock P/E": "pe_ratio",
        "Price to Earning": "pe_ratio",
        "Price to Earnings": "pe_ratio",
        "P/E": "pe_ratio",
        "Dividend Yield": "dividend_yield",
        "Div Yield": "dividend_yield",
        "ROCE %": "roce",
        "ROE %": "roe",
        "ROCE": "roce",
        "ROE": "roe",
        "Shares": "shares_outstanding",

        # Shareholding
        "Promoters": "promoter",
        "FIIs": "fii",
        "DIIs": "dii",
        "Public": "public",
        "Debt to equity": "debt_to_equity",
        "Debt / Eq": "debt_to_equity",
        "OPM": "operating_profit_margin",
        "Operating Profit Margin": "operating_profit_margin",
        "Government": "government",
        "Others": "others"
    }

    NORMALIZED_METRIC_MAP = {
        "revenue": "revenue",
        "sales": "revenue",
        "expenses": "expenses",
        "operating profit": "operating_profit",
        "opm": "operating_profit_margin",
        "other income": "other_income",
        "interest": "interest",
        "depreciation": "depreciation",
        "profit before tax": "profit_before_tax",
        "tax": "tax_pct",
        "net profit": "net_income",
        "eps": "eps",
        "equity capital": "equity_capital",
        "reserves": "reserves",
        "borrowings": "borrowings",
        "total liabilities": "total_liabilities",
        "fixed assets": "fixed_assets",
        "investments": "investments",
        "total assets": "total_assets",
        "cash from operating activity": "cash_flow_operating",
        "cash from investing activity": "cash_flow_investing",
        "cash from financing activity": "cash_flow_financing",
        "net cash flow": "net_cash_flow",
        "roce": "roce",
        "roe": "roe",
        "market cap": "market_cap",
        "current price": "share_price",
        "face value": "face_value",
        "book value": "book_value",
        "stock p/e": "pe_ratio",
        "pe ratio": "pe_ratio",
        "price to earning": "pe_ratio",
        "dividend yield": "dividend_yield",
        "div yield": "dividend_yield",
        "promoters": "promoter",
        "fiis": "fii",
        "diis": "dii",
        "public": "public",
        "government": "government",
        "debt to equity": "debt_to_equity",
        "debt / equity": "debt_to_equity",
        "opm": "operating_profit_margin",
        "operating profit margin": "operating_profit_margin",
        "others": "others"
    }
    
    def __init__(self, html: str, symbol: Optional[str] = None):
        self.soup = BeautifulSoup(html, 'lxml')
        self.symbol = symbol or self._extract_symbol()
        log.debug(f"Parser initialized for symbol: {self.symbol}")

    def _extract_symbol(self) -> Optional[str]:
        """Extract symbol from breadcrumbs or title"""
        title = self.soup.title.string if self.soup.title else ""
        # Title usually like "Reliance Industries Ltd share price... - External Source"
        # Sometimes symbols are in brackets: "Reliance Industries (RELIANCE) share price..."
        match = re.search(r'\(([A-Z0-9.]+)\)', title)
        if match:
            return match.group(1)
            
        match = re.search(r'([A-Z0-9.]+)\s+share price', title)
        return match.group(1) if match else None

    def get_company_name(self) -> str:
        """Extract company name from h1 tag"""
        h1 = self.soup.find('h1')
        return h1.text.strip() if h1 else "Unknown"

    def get_website_url(self) -> Optional[str]:
        """Extract company website URL from links section"""
        # Look for div with class company-links
        links_div = self.soup.find('div', class_='company-links')
        if links_div:
            # Usually the first link or one with 'target="_blank"'
            # Or text like "Company Website"
            for a in links_div.find_all('a', href=True):
                href = a['href']
                if "external-source-1.com" not in href and "javascript" not in href:
                    return href
        return None

    def get_ratios(self) -> Dict[str, Any]:
        """
        Extract numeric constants like Face Value.
        Market Cap and Ratios are EXCLUDED.
        """
        constants = {}
        ratios_container = self.soup.find('ul', id='top-ratios') or self.soup.find('div', id='top-ratios')
        
        if not ratios_container:
            ratios_container = self.soup.find('div', class_='company-ratios')
            
        if ratios_container:
            items = ratios_container.find_all('li')
            for item in items:
                name_el = item.find('span', class_='name')
                value_el = item.find('span', class_='value') or item.find('span', class_='number')
                
                if name_el and value_el:
                    raw_name = name_el.text.strip().replace(':', '')
                    
                    metric_key = self._resolve_metric_name(raw_name)
                    
                    if metric_key:
                        name = metric_key
                        raw_val = value_el.text.strip()
                        clean_val = re.sub(r'[\n\t\r₹%,]', '', raw_val)
                        clean_val = clean_val.replace('Cr.', '').strip()
                        
                        try:
                            if '.' in clean_val:
                                constants[name] = float(clean_val)
                            else:
                                constants[name] = int(clean_val)
                        except ValueError:
                            constants[name] = clean_val
        
        log.info(f"Extracted {len(constants)} constants")
        return constants

    def _resolve_metric_name(self, raw_label: str) -> Optional[str]:
        """Resolve a raw label to a normalized metric key using fuzzy matching."""
        label = raw_label.lower().strip().replace(':', '')
        
        # 1. Exact match lookup (fast)
        for key, val in self.NORMALIZED_METRIC_MAP.items():
            if key == label:
                return val
                
        # 2. Fuzzy/contains match (slower but resilient)
        # Prioritize longer keys to avoid false positives (e.g. "tax" vs "profit before tax")
        sorted_keys = sorted(self.NORMALIZED_METRIC_MAP.keys(), key=len, reverse=True)
        
        for key in sorted_keys:
            if key in label:
                return self.NORMALIZED_METRIC_MAP[key]
                
        return None

    def _parse_table(self, table_el) -> Dict[str, Dict[str, Any]]:
        """
        Parse financial table into a year-keyed dictionary.
        Example: {"2023": {"revenue": 100, "expenses": 80}}
        """
        if not table_el:
            return {}
            
        headers = []
        thead = table_el.find('thead')
        if thead:
            headers = [" ".join(th.text.split()) for th in thead.find_all('th')]
            if headers and not headers[0]:
                headers[0] = "Metric"
        
        if not headers:
            first_row = table_el.find('tr')
            if first_row:
                headers = [td.text.strip() for td in first_row.find_all(['th', 'td']) if td.text.strip()]
        
        # We need a structure keyed by year (or date string from header)
        # data[year] = { metric_name: value }
        data = {}
        
        tbody = table_el.find('tbody') or table_el
        rows = tbody.find_all('tr')
        
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue
                
            raw_label = " ".join(cols[0].text.split())
            if raw_label in headers or 'Raw Data' in raw_label or 'Sort' in raw_label:
                continue
            
            target_key = self._resolve_metric_name(raw_label)
            if not target_key:
                continue
            
            for i, col in enumerate(cols[1:]):
                if i + 1 < len(headers):
                    period = headers[i + 1]
                    # Clean the period name (usually just Year or Month Year)
                    period = period.strip()
                    if period not in data:
                        data[period] = {}
                        
                    val = " ".join(col.text.split()).replace(',', '').replace('%', '')
                    try:
                        data[period][target_key] = float(val) if val and val != '' else None
                    except ValueError:
                        data[period][target_key] = val
            
        return data

    @classmethod
    def _resolve_metric_name(cls, raw_label: str) -> Optional[str]:
        """Map raw label text to a Fundametrics metric name with relaxed normalization."""
        if not raw_label:
            return None

        clean_label = " ".join(raw_label.split()).replace(' +', '').replace('+', '').strip()
        if clean_label in cls.METRIC_MAP:
            return cls.METRIC_MAP[clean_label]

        normalized = clean_label.lower()
        normalized = re.sub(r'\([^)]*\)', '', normalized)  # remove parenthetical units
        normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return cls.NORMALIZED_METRIC_MAP.get(normalized)

    # REMOVED get_ranges_tables to comply with Phase 1 rules

    def get_financial_tables(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Extract all financial tables (Quarters, P&L, Balance Sheet, Cash Flow)"""
        tables = {}
        sections = {
            'quarters': 'quarters',
            'income_statement': 'profit-loss',
            'balance_sheet': 'balance-sheet',
            'cash_flow': 'cash-flow',
            'ratios': 'ratios'
        }
        
        for name, div_id in sections.items():
            section_div = self.soup.find('section', id=div_id) or self.soup.find('div', id=div_id)
            if section_div:
                table_el = section_div.find('table', class_='data-table')
                if table_el:
                    tables[name] = self._parse_table(table_el)
                    log.debug(f"Parsed {name} table")
        return tables

    def get_shareholding_pattern(self) -> Dict[str, Dict[str, Any]]:
        """Extract shareholding pattern percentages"""
        # Note: We keep this as raw snapshots if available
        section = self.soup.find('section', id='shareholding')
        if section:
            table_el = section.find('table', class_='data-table')
            if table_el:
                return self._parse_table(table_el)
        return {}

    def parse_all(self) -> Dict[str, Any]:
        """Run all extraction methods and return structured raw data"""
        try:
            financial_tables = self.get_financial_tables()
            
            data = {
                "metadata": {
                    "company_name": self.get_company_name(),
                    "symbol": self.symbol,
                    "website_url": self.get_website_url(),
                    "constants": self.get_ratios(),
                },
                "financials": financial_tables,
                "shareholding": self.get_shareholding_pattern()
            }
            log.success(f"Successfully extracted raw data for {data['metadata']['company_name']}")
            return data
        except Exception as e:
            log.exception(f"Error parsing external source HTML: {e}")
            return {}


if __name__ == "__main__":
    # Test with dummy HTML or a local file if available
    pass
