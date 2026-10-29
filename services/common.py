"""Ortak sabitler — circular import önlemek için."""
from zoneinfo import ZoneInfo

TZ_ISTANBUL = ZoneInfo("Europe/Istanbul")

# Kısaltma -> Yahoo sembolu
ALIASES = {
    "BTC": "BTC-USD", "BITCOIN": "BTC-USD",
    "ETH": "ETH-USD", "ETHEREUM": "ETH-USD",
    "SOL": "SOL-USD", "XRP": "XRP-USD", "DOGE": "DOGE-USD",
    "XU100": "XU100.IS", "BIST100": "XU100.IS",
    "USD": "TRY=X", "USDTRY": "TRY=X", "DOLAR": "TRY=X",
    "EUR": "EURTRY=X", "EURTRY": "EURTRY=X", "EURO": "EURTRY=X",
    "EURUSD": "EURUSD=X",
    "GOLD": "GC=F", "ALTIN": "GC=F", "ONSALTIN": "GC=F",
}


def kind_of(sym: str) -> str:
    if sym.endswith(".IS"):
        return "bist"
    if sym.endswith("=X"):
        return "fx"
    if sym == "GC=F":
        return "commodity"
    if "-" in sym:
        return "crypto"
    return "us"


def currency_of(sym: str) -> str:
    if sym.endswith(".IS"):
        return "TRY"
    if sym.endswith("=X"):
        return {"TRY=X": "TRY", "EURTRY=X": "TRY", "EURUSD=X": "USD"}.get(sym, "TRY")
    if sym.endswith("-TRY"):
        return "TRY"
    return "USD"