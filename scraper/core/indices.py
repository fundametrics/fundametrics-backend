from typing import Dict, List

# Core indices and their key constituents
# Using symbols that are commonly available or recently requested
INDEX_CONSTITUENTS: Dict[str, List[str]] = {
    "SENSEX": [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
        "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
        "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
        "TITAN", "BAJFINANCE", "TATASTEEL", "NTPC", "M&M"
    ],
    "NIFTY 50": [
        "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
        "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
        "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
        "TITAN", "BAJFINANCE", "TATASTEEL", "NTPC", "M&M",
        "ADANIPORTS", "ADANIENT", "APOLLOHOSP", "BAJAJ-AUTO", "BAJAJFINSV",
        "BPCL", "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB",
        "DRREDDY", "EICHERMOT", "GRASIM", "HCLTECH", "HDFCLIFE",
        "HEROMOTOCO", "HINDALCO", "INDUSINDBK", "JSWSTEEL", "LTIM",
        "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE",
        "TATASTEEL", "TATAMOTORS", "TECHM", "ULTRACEMCO", "WIPRO"
    ],
    "BANK NIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", 
        "INDUSINDBK", "AUANK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB",
        "PNB", "BANKBARODA"
    ]
}

def get_constituents(index_name: str) -> List[str]:
    """Return constituent symbols for a given index name."""
    return INDEX_CONSTITUENTS.get(index_name.upper(), [])
