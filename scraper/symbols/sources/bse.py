"""BSE master list discovery source."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from typing import Iterable, List, Optional

import httpx

from scraper.symbols.normalize import normalise_exchange, normalise_symbol

BSE_MASTER_URL = "https://api.bseindia.com/BseIndiaAPI/api/GetMktCapitalList/w"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)


@dataclass(slots=True)
class BseSymbol:
    symbol: str
    company_name: Optional[str]
    exchange: str = "BSE"
    sector: Optional[str] = None


def fetch_bse_master(timeout: float = 30.0) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv"}
    params = {"group": ""}
    with httpx.Client(timeout=timeout) as client:
        response = client.get(BSE_MASTER_URL, headers=headers, params=params)
        response.raise_for_status()
        return response.text


def parse_bse_master(raw_csv: str) -> Iterable[BseSymbol]:
    reader = csv.DictReader(StringIO(raw_csv))
    for row in reader:
        raw_symbol = row.get("SC_CODE") or row.get("SCRIPCODE") or row.get("Security Code")
        if not raw_symbol:
            continue
        try:
            symbol = normalise_symbol(row.get("SC_NAME", raw_symbol))
        except ValueError:
            continue
        yield BseSymbol(
            symbol=symbol,
            company_name=row.get("SC_NAME") or row.get("Security Name") or None,
            exchange=normalise_exchange("BSE"),
            sector=row.get("SC_GROUP") or row.get("Group") or None,
        )


def fetch_symbols(timeout: float = 30.0) -> List[BseSymbol]:
    raw = fetch_bse_master(timeout=timeout)
    return list(parse_bse_master(raw))


__all__ = ["fetch_symbols", "BSE_MASTER_URL", "BseSymbol"]
