import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper.core.fetcher import Fetcher
from scraper.sources.screener import ScreenerScraper

SYMBOL = "TATASTEEL"
OUTPUT_DIR = Path("data/processed/tatasteel")
RAW_PATH = OUTPUT_DIR / "tatasteel_raw.json"
REPORT_PATH = Path("reports/tatasteel_data_quality.txt")


async def fetch_data() -> Dict:
    fetcher = Fetcher()
    scraper = ScreenerScraper(fetcher)
    return await scraper.scrape_stock(SYMBOL)


def _format_number(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, (int, float)):
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if abs(value) >= 1_000:
            return f"{value / 1_000:.1f}k"
        return f"{value:.0f}"
    return str(value)


def _latest_series(row: Dict[str, float], limit: int = 4) -> List[Tuple[str, float]]:
    items: List[Tuple[str, float]] = [(k, v) for k, v in row.items() if k != "Metric" and v not in (None, "")]
    if not items:
        return []
    return items[-limit:]


def _coverage(row: Dict[str, float]) -> Tuple[int, int]:
    values = [v for k, v in row.items() if k != "Metric"]
    present = len([v for v in values if isinstance(v, (int, float))])
    return present, len(values)


def summarize(data: Dict) -> str:
    lines: List[str] = []
    lines.append("FUNDAMETRICS SCRAPER DATA QUALITY REPORT")
    lines.append("Symbol: {}".format(SYMBOL))
    lines.append("Company: {}".format(data.get("company_name", "Unknown")))
    lines.append("")

    ratios = data.get("ratios", {}) or {}
    lines.append(f"Ratios captured: {len(ratios)}")
    for key, value in list(ratios.items())[:10]:
        lines.append(f"  - {key}: {_format_number(value)}")
    if len(ratios) > 10:
        lines.append(f"  ... ({len(ratios) - 10} additional ratios available)")
    lines.append("")

    financial_tables = data.get("financial_tables", {}) or {}
    quarters = financial_tables.get("Quarters") or []
    if quarters:
        lines.append("Quarterly metrics overview:")
        for row in quarters[:3]:
            metric = row.get("Metric", "Unknown")
            present, total = _coverage(row)
            latest = _latest_series(row)
            latest_str = ", ".join(f"{period}: {_format_number(value)}" for period, value in latest)
            lines.append(f"  • {metric} — data points: {present}/{total}")
            if latest_str:
                lines.append(f"      Latest: {latest_str}")
        remaining = len(quarters) - 3
        if remaining > 0:
            lines.append(f"  ... ({remaining} additional quarterly metrics available)")
    else:
        lines.append("Quarterly metrics: none detected")
    lines.append("")

    income_statement = financial_tables.get("income_statement")
    if isinstance(income_statement, dict):
        years = list(income_statement.keys())
        lines.append(f"Income statement periods captured: {len(years)}")
        sample_years = years[-4:]
        for year in sample_years:
            entry = income_statement.get(year, {})
            revenue = entry.get("revenue")
            profit = entry.get("net_income")
            lines.append(f"  - {year}: revenue {_format_number(revenue)}, net income {_format_number(profit)}")
    lines.append("")

    shareholding = data.get("shareholding") or {}
    lines.append("Shareholding snapshot:")
    for key, value in shareholding.items():
        lines.append(f"  - {key}: {value}")
    if not shareholding:
        lines.append("  (no shareholding data provided)")
    lines.append("")

    lines.append("Raw payload keys: {}".format(", ".join(sorted(data.keys()))))
    lines.append("Data quality note: inspect raw JSON for full fidelity.")
    return "\n".join(lines)


async def main() -> None:
    data = await fetch_data()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    report_text = summarize(data)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Saved raw data to {RAW_PATH}")
    print(f"Saved report to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
