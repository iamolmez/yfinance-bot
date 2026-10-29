"""Veri sağlayıcı soyutlama katmanı — Fallback zinciri destekli.

Kullanım:
    from services.data_providers import get_provider_chain
    provider = get_provider_chain()
    df = provider.get_history("THYAO.IS", "6mo")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import time
import threading

import pandas as pd

from config import CACHE_TTL, HISTORY_PERIOD, QUOTE_PERIOD
from services.common import TZ_ISTANBUL, ALIASES, kind_of, currency_of

# Global name cache (thread-safe via locks in get_name)
_name_cache: dict = {}


@dataclass
class Quote:
    """Standartlaştırılmış fiyat verisi."""
    symbol: str
    price: float
    prev_close: float
    change: float
    change_pct: float
    high: float
    low: float
    volume: int
    kind: str
    currency: str
    timestamp: float


class DataProvider(ABC):
    """Tüm veri sağlayıcıları için temel arayüz."""

    name: str = "base"
    requires_api_key: bool = False

    def __init__(self):
        self._cache: dict = {}
        self._lock = threading.Lock()

    def _cache_key(self, symbol: str, period: str, interval: str = "1d") -> tuple:
        return (symbol, period, interval)

    def _get_cached(self, key: tuple) -> Optional[pd.DataFrame]:
        with self._lock:
            hit = self._cache.get(key)
            if hit and time.time() - hit["ts"] < CACHE_TTL:
                return hit["df"]
        return None

    def _set_cached(self, key: tuple, df: pd.DataFrame) -> None:
        with self._lock:
            self._cache[key] = {"ts": time.time(), "df": df}

    @abstractmethod
    def _fetch_history(self, symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        """Sağlayıcıya özel veri çekme mantığı."""
        pass

    def get_history(self, symbol: str, period: Optional[str] = None, interval: str = "1d") -> Optional[pd.DataFrame]:
        """Önbellekli geçmiş veri çeker."""
        period = period or HISTORY_PERIOD
        key = self._cache_key(symbol, period, interval)

        cached = self._get_cached(key)
        if cached is not None:
            return cached

        df = self._fetch_history(symbol, period, interval)
        if df is not None and not df.empty and "Close" in df.columns:
            df = df.dropna(subset=["Close"]).sort_index()
            if df.index.tz is not None:
                df.index = df.index.tz_convert(TZ_ISTANBUL).tz_localize(None)
            self._set_cached(key, df)
            return df
        return None

    def _quote_from_df(self, df: pd.DataFrame, symbol: str) -> Optional[Quote]:
        """DataFrame'den standart Quote nesnesi oluşturur."""
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
        volume = 0
        if "Volume" in df:
            vol_val = df["Volume"].iloc[-1]
            if pd.notna(vol_val):
                volume = int(vol_val)
        return Quote(
            symbol=symbol,
            price=price,
            prev_close=prev,
            change=change,
            change_pct=change_pct,
            high=high,
            low=low,
            volume=volume,
            kind=kind_of(symbol),
            currency=currency_of(symbol),
            timestamp=time.time(),
        )

    def get_quote(self, symbol: str) -> Optional[Quote]:
        df = self.get_history(symbol, period=QUOTE_PERIOD)
        return self._quote_from_df(df, symbol) if df is not None else None

    def get_quotes_batch(self, symbols: list[str], period: Optional[str] = None) -> dict[str, Quote]:
        """Toplu fiyat çekimi — alt sınıflar override edebilir."""
        period = period or QUOTE_PERIOD
        out: dict[str, Quote] = {}
        for sym in symbols:
            q = self.get_quote(sym)
            if q:
                out[sym] = q
        return out

    def get_name(self, symbol: str, ttl: int = 86400) -> str:
        """Şirket adı (global name cache kullanır)."""
        now = time.time()
        with threading.Lock():
            hit = _name_cache.get(symbol)
            if hit and now - hit["ts"] < ttl:
                return hit["name"]
        name = symbol
        try:
            name = self._fetch_name(symbol) or symbol
        except Exception:
            pass
        with threading.Lock():
            _name_cache[symbol] = {"ts": now, "name": name}
        return name

    def _fetch_name(self, symbol: str) -> Optional[str]:
        """Sağlayıcıya özel isim çekme."""
        return None

    def resolve_symbol(self, raw: str) -> Optional[tuple[str, str, str]]:
        """Kullanıcı girdisini doğrulanmış sembole çevirir."""
        for cand in self._candidates(raw):
            df = self.get_history(cand, period="5d")
            if df is not None and not df.empty:
                return cand, kind_of(cand), currency_of(cand)
        return None

    def _candidates(self, raw: str) -> list[str]:
        """Yahoo sembol adayları — yfinance uyumlu."""
        s = raw.strip().upper()
        out: list[str] = []
        if s in ALIASES:
            out.append(ALIASES[s])
        out.append(s)
        if "." not in s and "-" not in s and "=" not in s and s.isalnum() and len(s) <= 7:
            out.append(s + ".IS")
        if "." not in s and "=" not in s and "X" not in s[-3:]:
            out.append(s + "-USD")
        return list(dict.fromkeys(out))


class YFinanceProvider(DataProvider):
    """Yahoo Finance (yfinance) sağlayıcısı — API anahtarı gerekmez."""

    name = "yfinance"
    requires_api_key = False

    def __init__(self):
        super().__init__()
        import yfinance as yf
        self._yf = yf

    def _fetch_history(self, symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        try:
            df = self._yf.Ticker(symbol).history(
                period=period, interval=interval, auto_adjust=False
            )
            return df
        except Exception:
            return None

    def _fetch_name(self, symbol: str) -> Optional[str]:
        try:
            info = self._yf.Ticker(symbol).info
            return info.get("shortName") or info.get("longName")
        except Exception:
            return None

    def get_quotes_batch(self, symbols: list[str], period: Optional[str] = None) -> dict[str, Quote]:
        """yfinance download ile toplu çekim (daha hızlı)."""
        period = period or QUOTE_PERIOD
        out: dict[str, Quote] = {}
        todo: list[str] = []
        now = time.time()

        # Önbellekten oku
        for sym in symbols:
            key = self._cache_key(sym, period, "1d")
            with self._lock:
                hit = self._cache.get(key)
                if hit and now - hit["ts"] < CACHE_TTL:
                    q = self._quote_from_df(hit["df"], sym)
                    if q:
                        out[sym] = q
                        continue
            todo.append(sym)

        if not todo:
            return out

        try:
            df = self._yf.download(
                todo, period=period, interval="1d",
                auto_adjust=False, progress=False, threads=False,
                group_by="ticker",
            )
        except Exception:
            df = pd.DataFrame()

        if df is None or df.empty:
            return out

        if isinstance(df.columns, pd.MultiIndex):
            for sym in todo:
                if sym not in df.columns.get_level_values(0):
                    continue
                sub = df[sym]
                if isinstance(sub.columns, pd.MultiIndex):
                    sub.columns = sub.columns.get_level_values(-1)
                q = self._quote_from_df(sub, sym)
                if q:
                    out[sym] = q
                    with self._lock:
                        self._cache[(sym, period, "1d")] = {"ts": now, "df": sub}
        else:
            sym = todo[0]
            q = self._quote_from_df(df, sym)
            if q:
                out[sym] = q
        return out


class AlphaVantageProvider(DataProvider):
    """Alpha Vantage sağlayıcısı — API key gerekli (ALPHAVANTAGE_API_KEY)."""

    name = "alphavantage"
    requires_api_key = True
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        import os
        self.api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        self._session = None

    def _fetch_history(self, symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        if not self.api_key:
            return None
        # Alpha Vantage sembol formatı: IBM, IBM.DEX (forex), BTC/USD (crypto)
        av_symbol = self._to_av_symbol(symbol)
        if not av_symbol:
            return None

        try:
            import requests
            if self._session is None:
                self._session = requests.Session()

            # Günlük veri için TIME_SERIES_DAILY_ADJUSTED
            params = {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": av_symbol,
                "apikey": self.api_key,
                "outputsize": "full" if period in ("1y", "2y", "5y", "10y") else "compact",
                "datatype": "json",
            }
            resp = self._session.get(self.BASE_URL, params=params, timeout=10)
            data = resp.json()

            if "Time Series (Daily)" not in data:
                return None

            ts = data["Time Series (Daily)"]
            rows = []
            for date_str, vals in ts.items():
                rows.append({
                    "Date": date_str,
                    "Open": float(vals["1. open"]),
                    "High": float(vals["2. high"]),
                    "Low": float(vals["3. low"]),
                    "Close": float(vals["4. close"]),
                    "Adj Close": float(vals["5. adjusted close"]),
                    "Volume": int(vals["6. volume"]),
                })
            df = pd.DataFrame(rows)
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception:
            return None

    def _to_av_symbol(self, symbol: str) -> Optional[str]:
        """Yahoo sembolünü Alpha Vantage formatına çevirir."""
        if symbol.endswith(".IS"):  # BIST
            return symbol[:-3] + ".IST"
        if symbol.endswith("=X"):  # Forex
            if symbol == "TRY=X":
                return "USD/TRY"
            if symbol == "EURTRY=X":
                return "EUR/TRY"
            if symbol == "EURUSD=X":
                return "EUR/USD"
        if symbol == "GC=F":  # Gold
            return "GLD"  # GLD ETF jako proxy
        if "-" in symbol:  # Crypto
            return symbol.replace("-", "/")
        return symbol  # US stocks


class TwelveDataProvider(DataProvider):
    """Twelve Data sağlayıcısı — API key gerekli (TWELVEDATA_API_KEY)."""

    name = "twelvedata"
    requires_api_key = True
    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        import os
        self.api_key = api_key or os.getenv("TWELVEDATA_API_KEY")
        self._session = None

    def _fetch_history(self, symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        if not self.api_key:
            return None
        td_symbol = self._to_td_symbol(symbol)
        if not td_symbol:
            return None

        try:
            import requests
            if self._session is None:
                self._session = requests.Session()

            outputsize = 5000 if period in ("1y", "2y", "5y", "10y") else 100
            params = {
                "symbol": td_symbol,
                "interval": "1day",
                "outputsize": outputsize,
                "apikey": self.api_key,
                "format": "JSON",
            }
            resp = self._session.get(f"{self.BASE_URL}/time_series", params=params, timeout=10)
            data = resp.json()

            if "values" not in data:
                return None

            rows = []
            for v in data["values"]:
                rows.append({
                    "Date": v["datetime"],
                    "Open": float(v["open"]),
                    "High": float(v["high"]),
                    "Low": float(v["low"]),
                    "Close": float(v["close"]),
                    "Volume": int(v.get("volume", 0)),
                })
            df = pd.DataFrame(rows)
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
            df.sort_index(inplace=True)
            return df
        except Exception:
            return None

    def _to_td_symbol(self, symbol: str) -> Optional[str]:
        """Yahoo sembolünü Twelve Data formatına çevirir."""
        # Twelve Data sembolleri Yahoo'ya benzer
        if symbol.endswith(".IS"):
            return symbol  # BIST desteklenir
        if symbol.endswith("=X"):
            return symbol.replace("=X", "/")  # USD/TRY formatı
        if symbol == "GC=F":
            return "XAU/USD"
        return symbol


class PolygonProvider(DataProvider):
    """Polygon.io sağlayıcısı — API key gerekli (POLYGON_API_KEY)."""

    name = "polygon"
    requires_api_key = True
    BASE_URL = "https://api.polygon.io"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        import os
        self.api_key = api_key or os.getenv("POLYGON_API_KEY")
        self._session = None

    def _fetch_history(self, symbol: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        if not self.api_key:
            return None
        poly_symbol = self._to_polygon_symbol(symbol)
        if not poly_symbol:
            return None

        try:
            import requests
            if self._session is None:
                self._session = requests.Session()

            # Tarih aralığı hesapla
            from datetime import date, timedelta
            end = date.today()
            days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "10y": 3650}
            days = days_map.get(period, 180)
            start = end - timedelta(days=days)

            params = {
                "adjusted": "true",
                "sort": "asc",
                "limit": 50000,
                "apiKey": self.api_key,
            }
            resp = self._session.get(
                f"{self.BASE_URL}/v2/aggs/ticker/{poly_symbol}/range/1/day/{start}/{end}",
                params=params, timeout=10
            )
            data = resp.json()

            if "results" not in data:
                return None

            rows = []
            for v in data["results"]:
                rows.append({
                    "Date": pd.Timestamp(v["t"], unit="ms", tz="UTC").tz_convert(TZ_ISTANBUL).tz_localize(None),
                    "Open": v["o"],
                    "High": v["h"],
                    "Low": v["l"],
                    "Close": v["c"],
                    "Volume": v["v"],
                })
            df = pd.DataFrame(rows)
            df.set_index("Date", inplace=True)
            return df
        except Exception:
            return None

    def _to_polygon_symbol(self, symbol: str) -> Optional[str]:
        """Yahoo sembolünü Polygon formatına çevirir."""
        if symbol.endswith(".IS"):
            return "X:" + symbol[:-3]  # BIST için X: prefix
        if symbol.endswith("=X"):
            return "C:" + symbol[:-2]  # Forex için C: prefix
        if symbol == "GC=F":
            return "C:XAUUSD"
        if "-" in symbol:
            return "X:" + symbol.replace("-", "")  # Crypto
        return symbol  # US stocks


class FallbackProvider:
    """Fallback zinciri — sağlayıcıları sırayla dener (DataProvider olmayan composite)."""

    name = "fallback"
    requires_api_key = False

    def __init__(self, providers: list[DataProvider]):
        self.providers = providers

    def get_history(self, symbol: str, period: Optional[str] = None, interval: str = "1d") -> Optional[pd.DataFrame]:
        for p in self.providers:
            df = p.get_history(symbol, period, interval)
            if df is not None and not df.empty:
                return df
        return None

    def get_quote(self, symbol: str) -> Optional[Quote]:
        for p in self.providers:
            q = p.get_quote(symbol)
            if q is not None:
                return q
        return None

    def get_quotes_batch(self, symbols: list[str], period: Optional[str] = None) -> dict[str, Quote]:
        # İlk sağlayıcı toplu çekmeyi destekliyorsa onu kullan
        for p in self.providers:
            if hasattr(p, 'get_quotes_batch'):
                result = p.get_quotes_batch(symbols, period)
                if result:
                    return result
        # Fallback: tek tek çek
        out: dict[str, Quote] = {}
        for sym in symbols:
            q = self.get_quote(sym)
            if q:
                out[sym] = q
        return out

    def resolve_symbol(self, raw: str) -> Optional[tuple[str, str, str]]:
        for p in self.providers:
            res = p.resolve_symbol(raw)
            if res:
                return res
        return None

    def get_name(self, symbol: str, ttl: int = 86400) -> str:
        for p in self.providers:
            name = p.get_name(symbol, ttl)
            if name and name != symbol:
                return name
        return symbol


# Global provider chain (lazy init)
_provider_chain: Optional[FallbackProvider] = None
_provider_lock = threading.Lock()


def get_provider_chain() -> FallbackProvider:
    """Sağlayıcı zincirini oluşturur/döndürür (config'e göre sıralı)."""
    global _provider_chain
    if _provider_chain is not None:
        return _provider_chain

    with _provider_lock:
        if _provider_chain is not None:
            return _provider_chain

        from config import DATA_PROVIDERS
        provider_names = [p.strip().lower() for p in DATA_PROVIDERS.split(",")] if DATA_PROVIDERS else ["yfinance"]

        providers: list[DataProvider] = []
        for name in provider_names:
            if name == "yfinance":
                providers.append(YFinanceProvider())
            elif name == "alphavantage":
                providers.append(AlphaVantageProvider())
            elif name == "twelvedata":
                providers.append(TwelveDataProvider())
            elif name == "polygon":
                providers.append(PolygonProvider())
            # Bilinmeyen sağlayıcı atlanır

        if not providers:
            providers.append(YFinanceProvider())  # Güvenli fallback

        _provider_chain = FallbackProvider(providers)
        return _provider_chain