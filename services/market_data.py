"""Piyasa verisi servisi.

Tek veri kaynagi: yfinance (Yahoo Finance). BIST, ABD hisseleri, kripto ve
doviz kurlari ayni API uzerinden cekilir - API anahtari gerekmez.

Sembol kurallari:
- BIST   : THYAO.IS, GARAN.IS, XU100.IS ...
- ABD    : AAPL, TSLA, NVDA ...
- Kripto : BTC-USD, ETH-USD ...
- Doviz  : TRY=X (USD/TRY), EURTRY=X, EURUSD=X ...
"""
import threading
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from config import CACHE_TTL, HISTORY_PERIOD, QUOTE_PERIOD

TZ_ISTANBUL = ZoneInfo("Europe/Istanbul")

# Kisaltma -> Yahoo sembolu
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

_cache: dict = {}
_lock = threading.Lock()
_name_cache: dict = {}


def _candidates(raw: str) -> list[str]:
    """Kullanici girdisinden denenecek sembol adaylarini uretir."""
    s = raw.strip().upper()
    out: list[str] = []
    if s in ALIASES:
        out.append(ALIASES[s])
    out.append(s)
    # BIST tahmini: noktasiz, kisa, harf-rakam karisimi
    if "." not in s and "-" not in s and "=" not in s and s.isalnum() and len(s) <= 7:
        out.append(s + ".IS")
    # Kripto tahmini
    if "." not in s and "=" not in s and "X" not in s[-3:]:
        out.append(s + "-USD")
    # Tekrarlari temizle
    return list(dict.fromkeys(out))


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


def get_history(sym: str, period: str | None = None, interval: str = "1d") -> pd.DataFrame | None:
    """Gunluk OHLCV verisi (artan tarih sirasinda). Onbellekli."""
    period = period or HISTORY_PERIOD
    key = (sym, period, interval)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit["ts"] < CACHE_TTL:
            return hit["df"]
    try:
        df = yf.Ticker(sym).history(
            period=period, interval=interval, auto_adjust=False
        )
    except Exception:
        return None
    if df is None or df.empty or "Close" not in df.columns:
        return None
    df = df.dropna(subset=["Close"]).sort_index()
    if df.index.tz is not None:
        df.index = df.index.tz_convert(TZ_ISTANBUL).tz_localize(None)
    with _lock:
        _cache[key] = {"ts": now, "df": df}
    return df


def resolve_symbol(raw: str) -> tuple[str, str, str] | None:
    """Sembol girdisini dogrulanmis sembole cevirir. (sembol, tur, para) dondurur."""
    for cand in _candidates(raw):
        df = get_history(cand, period="5d")
        if df is not None and not df.empty:
            return cand, kind_of(cand), currency_of(cand)
    return None


def get_name(sym: str, ttl: int = 86400) -> str:
    """Sirket adi (yavas istek, 24 saat onbelleklenir)."""
    now = time.time()
    with _lock:
        hit = _name_cache.get(sym)
        if hit and now - hit["ts"] < ttl:
            return hit["name"]
    name = sym
    try:
        info = yf.Ticker(sym).info
        name = info.get("shortName") or info.get("longName") or sym
    except Exception:
        pass
    with _lock:
        _name_cache[sym] = {"ts": now, "name": name}
    return name


def _quote_from_df(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty or "Close" not in df:
        return None
    closes = df["Close"].dropna()
    if len(closes) == 0:
        return None
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else price
    change = price - prev
    change_pct = (change / prev * 100) if prev else 0.0
    high = float(df["High"].max()) if "High" in df else price
    low = float(df["Low"].min()) if "Low" in df else price
    volume = int(df["Volume"].iloc[-1]) if "Volume" in df else 0
    return {
        "symbol": None,  # cagiran doldurur
        "price": price,
        "prev_close": prev,
        "change": change,
        "change_pct": change_pct,
        "high": high,
        "low": low,
        "volume": volume,
    }


def get_quote(sym: str) -> dict | None:
    df = get_history(sym, period=QUOTE_PERIOD)
    q = _quote_from_df(df)
    if q:
        q["symbol"] = sym
        q["kind"] = kind_of(sym)
        q["currency"] = currency_of(sym)
    return q


def get_quotes_batch(symbols: list[str], period: str | None = None) -> dict[str, dict]:
    """Birden fazla sembolun fiyatini TEK istekte ceker (tarama icin hizli)."""
    period = period or QUOTE_PERIOD
    out: dict[str, dict] = {}
    todo: list[str] = []
    now = time.time()

    # Onbellekten oku
    for sym in symbols:
        key = (sym, period, "1d")
        with _lock:
            hit = _cache.get(key)
            if hit and now - hit["ts"] < CACHE_TTL:
                q = _quote_from_df(hit["df"])
                if q:
                    q["symbol"] = sym
                    q["kind"] = kind_of(sym)
                    q["currency"] = currency_of(sym)
                    out[sym] = q
                    continue
        todo.append(sym)

    if not todo:
        return out

    try:
        df = yf.download(
            todo, period=period, interval="1d",
            auto_adjust=False, progress=False, threads=False,
            group_by="ticker",
        )
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        return out

    # MultiIndex mi?
    if isinstance(df.columns, pd.MultiIndex):
        for sym in todo:
            if sym not in df.columns.get_level_values(0):
                continue
            sub = df[sym]
            if isinstance(sub.columns, pd.MultiIndex):
                sub.columns = sub.columns.get_level_values(-1)
            q = _quote_from_df(sub)
            if q:
                q["symbol"] = sym
                q["kind"] = kind_of(sym)
                q["currency"] = currency_of(sym)
                out[sym] = q
                with _lock:
                    _cache[(sym, period, "1d")] = {"ts": now, "df": sub}
    else:
        # Tek sembol geldi
        sym = todo[0]
        q = _quote_from_df(df)
        if q:
            q["symbol"] = sym
            q["kind"] = kind_of(sym)
            q["currency"] = currency_of(sym)
            out[sym] = q
    return out


def get_fx_rate(pair: str = "TRY=X") -> float | None:
    """Doviz kuru. Ornek: TRY=X -> 1 USD kac TRY."""
    df = get_history(pair, period="5d")
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[-1])


def is_market_open(sym: str) -> bool:
    """Yaklasik piyasa aciklik kontrolu. Kripto her zaman acik."""
    kind = kind_of(sym)
    if kind in ("crypto", "fx", "commodity"):
        return True
    now = datetime.now(TZ_ISTANBUL)
    if now.weekday() >= 5:  # hafta sonu
        return False
    t = now.time()
    if kind == "bist":
        return dtime(9, 0) <= t <= dtime(18, 0)
    # ABD: NYSE 9:30-16:00 ET. TR saati yaklasik (kis saati ET = TR - 8)
    return dtime(16, 0) <= t <= dtime(23, 30)


def market_hours_text(sym: str) -> str:
    kind = kind_of(sym)
    if kind in ("crypto", "fx", "commodity"):
        return "7/24 açık"
    if kind == "bist":
        return "Hafta içi 09:00–18:00 (TR)"
    return "Hafta içi ~16:00–23:30 (TR)"


def get_news(sym: str, limit: int = 5) -> list[dict]:
    """Sembol icin son haber basliklari (yfinance). Bos liste donulebilir."""
    try:
        items = yf.Ticker(sym).news
    except Exception:
        return []
    out: list[dict] = []
    for it in (items or [])[:limit]:
        title = (it.get("title") or "").strip()
        link = (it.get("link") or "").strip()
        if title:
            out.append({"title": title, "link": link})
    return out
