"""NSE master list discovery source."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable, List, Optional

import httpx

from scraper.symbols.normalize import normalise_exchange, normalise_symbol

NSE_MASTER_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)


@dataclass(slots=True)
class NseSymbol:
    symbol: str
    company_name: Optional[str]
    exchange: str = "NSE"
    sector: Optional[str] = None


def fetch_nse_master(timeout: float = 30.0) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv"}
    with httpx.Client(timeout=timeout) as client:
        response = client.get(NSE_MASTER_URL, headers=headers)
        response.raise_for_status()
        return response.text


def parse_nse_master(raw_csv: str) -> Iterable[NseSymbol]:
    reader = csv.DictReader(StringIO(raw_csv))
    for row in reader:
        try:
            symbol = normalise_symbol(row.get("SYMBOL", ""))
        except ValueError:
            continue
        yield NseSymbol(
            symbol=symbol,
            company_name=row.get("NAME OF COMPANY") or None,
            exchange=normalise_exchange("NSE"),
            sector=row.get("INDUSTRY") or None,
        )


def fetch_symbols(timeout: float = 30.0) -> List[NseSymbol]:
    raw = fetch_nse_master(timeout=timeout)
    return list(parse_nse_master(raw))


__all__ = ["fetch_symbols", "NSE_MASTER_URL", "NseSymbol"]
