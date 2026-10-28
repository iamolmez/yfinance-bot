"""Temel (fundamental) analiz.

Sirketin finansal sagligini degerlendirir: degerleme (F/K, P/B), karlilik,
borc, buyume ve temettu. yfinance info verisi kullanilir ve 24 saat onbelleklenir
(inf verisi yavas cekildigi icin).

BILGI: Yatirim tavsiyesi degildir; sirket finansallarina dair bilgidir.
"""
import time

import yfinance as yf

# sembol -> (ts, dict)
_cache: dict = {}
_TTL = 86400  # 24 saat


def get_fundamentals(sym: str, ttl: int = _TTL) -> dict | None:
    """Bir sembolun temel verilerini toplar. Eksik veri -> None alan."""
    now = time.time()
    hit = _cache.get(sym)
    if hit and now - hit["ts"] < ttl:
        return hit["data"]

    try:
        info = yf.Ticker(sym).info
    except Exception:
        return None
    if not info or not info.get("shortName"):
        return None

    def _num(key, divisor=1.0):
        v = info.get(key)
        try:
            return round(float(v) / divisor, 2) if v is not None else None
        except (TypeError, ValueError):
            return None

    data = {
        "name": info.get("shortName") or info.get("longName") or sym,
        "currency": info.get("currency", "USD"),
        "market_cap": _num("marketCap", 1e9),           # milyar
        "pe": _num("trailingPE"),                        # F/K
        "pb": _num("priceToBook"),                       # P/B
        "roe": _num("returnOnEquity"),                   # oran (0.15 = %15)
        "profit_margin": _num("profitMargins"),
        "revenue_growth": _num("revenueGrowth"),
        "debt_to_equity": _num("debtToEquity"),
        "dividend_yield": _num("dividendYield"),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
    }
    _cache[sym] = {"ts": now, "data": data}
    return data


def score_fundamentals(f: dict | None) -> tuple[int, str]:
    """0-100 temel skor + etiket. Yetersiz veride (0, 'veri yok')."""
    if not f:
        return 0, "veri yok"
    score = 0
    n = 0

    # F/K: dusuk iyi (pozitifse). 0-20 bandinda 20 -> 0, 0-10 -> daha iyi
    pe = f.get("pe")
    if pe and pe > 0:
        n += 1
        if pe < 10:
            score += 20
        elif pe < 15:
            score += 14
        elif pe < 20:
            score += 8
        elif pe < 30:
            score += 3
        else:
            score += 0

    # P/B: dusuk iyi
    pb = f.get("pb")
    if pb and pb > 0:
        n += 1
        if pb < 1:
            score += 15
        elif pb < 2:
            score += 11
        elif pb < 4:
            score += 6
        else:
            score += 1

    # ROE: yuksek iyi (oran olarak, %15 = 0.15)
    roe = f.get("roe")
    if roe is not None:
        n += 1
        if roe > 0.20:
            score += 20
        elif roe > 0.12:
            score += 14
        elif roe > 0.05:
            score += 7
        elif roe >= 0:
            score += 2
        else:
            score += 0

    # Kar marji
    pm = f.get("profit_margin")
    if pm is not None:
        n += 1
        if pm > 0.25:
            score += 15
        elif pm > 0.12:
            score += 10
        elif pm > 0.05:
            score += 6
        elif pm >= 0:
            score += 2
        else:
            score += 0

    # Buyume
    rg = f.get("revenue_growth")
    if rg is not None:
        n += 1
        if rg > 0.20:
            score += 15
        elif rg > 0.10:
            score += 10
        elif rg > 0:
            score += 5
        else:
            score += 0

    # Borc/ozkaynak: dusuk iyi
    dte = f.get("debt_to_equity")
    if dte is not None:
        n += 1
        if dte < 50:
            score += 15
        elif dte < 100:
            score += 10
        elif dte < 200:
            score += 5
        else:
            score += 0

    # Temettu verimi: yuksek iyi (0.03 = %3)
    dy = f.get("dividend_yield")
    if dy is not None:
        n += 1
        if dy > 0.04:
            score += 10
        elif dy > 0.02:
            score += 7
        elif dy > 0:
            score += 4
        else:
            score += 0

    if n == 0:
        return 0, "yetersiz veri"
    # Ortalama metrik puani (0-15 bandinda) -> 0-100 olcegi
    avg = score / n
    total = min(100, round(avg / 15 * 100))
    if total >= 70:
        label = "🟢 Güçlü"
    elif total >= 45:
        label = "🔵 Makul"
    elif total >= 25:
        label = "🟡 Zayıf"
    else:
        label = "🔴 Zayıf"
    return total, label


def fundamentals_text(f: dict | None) -> str:
    """Temel veriyi tek satirlik metin olarak formatlar."""
    if not f:
        return "Temel veri alınamadı."
    score, label = score_fundamentals(f)
    parts = [
        f"<b>Temel Analiz:</b> {label} (skor {score}/100)",
    ]
    if f.get("pe") is not None:
        parts.append(f"F/K: {f['pe']:.1f}")
    if f.get("pb") is not None:
        parts.append(f"P/B: {f['pb']:.1f}")
    if f.get("roe") is not None:
        parts.append(f"ROE: %{f['roe']*100:.0f}")
    if f.get("profit_margin") is not None:
        parts.append(f"Kar marjı: %{f['profit_margin']*100:.0f}")
    if f.get("revenue_growth") is not None:
        parts.append(f"Büyüme: %{f['revenue_growth']*100:.0f}")
    if f.get("debt_to_equity") is not None:
        parts.append(f"Borç/Özkaynak: {f['debt_to_equity']:.0f}")
    if f.get("dividend_yield") is not None:
        parts.append(f"Temettü: %{f['dividend_yield']*100:.1f}")
    if f.get("market_cap") is not None:
        parts.append(f"Piyasa değeri: {f['market_cap']:.1f} milyar {f.get('currency','')}")
    if f.get("sector"):
        parts.append(f"Sektör: {f['sector']}")
    return " | ".join(parts)
