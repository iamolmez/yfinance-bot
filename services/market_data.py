"""Piyasa verisi servisi — Fallback zinciri destekli.

Veri sağlayıcıları: yfinance (varsayılan), Alpha Vantage, Twelve Data, Polygon.
Sıralama DATA_PROVIDERS env değişkeniyle ayarlanır (örn: "yfinance,alphavantage").

Sembol kurallari:
- BIST   : THYAO.IS, GARAN.IS, XU100.IS ...
- ABD    : AAPL, TSLA, NVDA ...
- Kripto : BTC-USD, ETH-USD ...
- Doviz  : TRY=X (USD/TRY), EURTRY=X, EURUSD=X ...
"""
import threading
import time
from datetime import datetime, time as dtime

import pandas as pd

from config import CACHE_TTL, HISTORY_PERIOD, QUOTE_PERIOD, DATA_PROVIDERS
from services.data_providers import get_provider_chain, Quote as ProviderQuote
from services.common import TZ_ISTANBUL, ALIASES, kind_of, currency_of

_name_cache: dict = {}
_name_lock = threading.Lock()


def _provider_quote_to_dict(q: ProviderQuote) -> dict:
    """Provider Quote nesnesini dict'e çevirir (geriye uyumluluk)."""
    return {
        "symbol": q.symbol,
        "price": q.price,
        "prev_close": q.prev_close,
        "change": q.change,
        "change_pct": q.change_pct,
        "high": q.high,
        "low": q.low,
        "volume": q.volume,
        "kind": q.kind,
        "currency": q.currency,
    }


def get_history(sym: str, period: str | None = None, interval: str = "1d") -> pd.DataFrame | None:
    """Günlük OHLCV verisi (artan tarih sırasında). Önbellekli."""
    provider = get_provider_chain()
    return provider.get_history(sym, period, interval)


def resolve_symbol(raw: str) -> tuple[str, str, str] | None:
    """Sembol girdisini doğrulanmış sembole çevirir. (sembol, tür, para) döndürür."""
    provider = get_provider_chain()
    return provider.resolve_symbol(raw)


def get_name(sym: str, ttl: int = 86400) -> str:
    """Şirket adı (yavaş istek, 24 saat önbelleklenir)."""
    provider = get_provider_chain()
    return provider.get_name(sym, ttl)


def get_quote(sym: str) -> dict | None:
    provider = get_provider_chain()
    q = provider.get_quote(sym)
    return _provider_quote_to_dict(q) if q else None


def get_quotes_batch(symbols: list[str], period: str | None = None) -> dict[str, dict]:
    """Birden fazla sembolün fiyatını TEK istekte çeker (tarama için hızlı)."""
    provider = get_provider_chain()
    quotes = provider.get_quotes_batch(symbols, period)
    return {sym: _provider_quote_to_dict(q) for sym, q in quotes.items()}


def get_fx_rate(pair: str = "TRY=X") -> float | None:
    """Döviz kuru. Örnek: TRY=X -> 1 USD kaç TRY."""
    df = get_history(pair, period="5d")
    if df is None or df.empty:
        return None
    return float(df["Close"].iloc[-1])


def is_market_open(sym: str) -> bool:
    """Yaklaşık piyasa açıklık kontrolü. Kripto her zaman açık."""
    kind = kind_of(sym)
    if kind in ("crypto", "fx", "commodity"):
        return True
    now = datetime.now(TZ_ISTANBUL)
    if now.weekday() >= 5:  # hafta sonu
        return False
    t = now.time()
    if kind == "bist":
        return dtime(9, 0) <= t <= dtime(18, 0)
    # ABD: NYSE 9:30-16:00 ET. TR saati yaklaşık (kış saati ET = TR - 8)
    return dtime(16, 0) <= t <= dtime(23, 30)


def market_hours_text(sym: str) -> str:
    kind = kind_of(sym)
    if kind in ("crypto", "fx", "commodity"):
        return "7/24 açık"
    if kind == "bist":
        return "Hafta içi 09:00–18:00 (TR)"
    return "Hafta içi ~16:00–23:30 (TR)"


def get_news(sym: str, limit: int = 5) -> list[dict]:
    """Sembol için son haber başlıkları (yfinance — provider bağımsız)."""
    # Haberler henüz provider'larda yok, yfinance kullan
    try:
        import yfinance as yf
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