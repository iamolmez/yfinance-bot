"""Sinyal motoru.

Teknik gostergelerden puanlama ile kisa vadeli AL / SAT / NOTR sinyali uretir.
BILGI: Bu araclar yatirim tavsiyesi DEGILDIR. Sadece matematiksel gostergelerdir.
"""
from services import indicators as ind
from services import market_data as md


def score_symbol(sym: str) -> dict | None:
    """Bir sembol icin sinyal skoru ve gerekcelerini dondurur."""
    df = md.get_history(sym, period="6mo")
    if df is None or df.empty:
        return None
    try:
        a = ind.full_analysis(df)
    except Exception:
        return None

    price = a["price"]
    reasons: list[str] = []
    score = 0

    # 1) RSI
    r = a["rsi"]
    if r < 30:
        score += 2
        reasons.append(f"RSI {r:.0f} → aşırı satım, tepki alımı olası")
    elif r < 40:
        score += 1
        reasons.append(f"RSI {r:.0f} → zayıf, alım bölgesine yakın")
    elif r > 70:
        score -= 2
        reasons.append(f"RSI {r:.0f} → aşırı alım, kar satışı riski")
    elif r > 60:
        score -= 1
        reasons.append(f"RSI {r:.0f} → güçlü, satım bölgesine yakın")

    # 2) MACD
    if a["macd_hist"] > 0:
        score += 1
        if a["macd_hist"] > a["macd_hist_prev"]:
            score += 1
            reasons.append("MACD pozitif ve güçleniyor")
        else:
            reasons.append("MACD pozitif ama ivme kaybediyor")
    else:
        score -= 1
        if a["macd_hist"] < a["macd_hist_prev"]:
            score -= 1
            reasons.append("MACD negatif ve zayıflıyor")
        else:
            reasons.append("MACD negatif ama toparlanıyor")

    # 3) SMA konumu
    if price > a["sma20"]:
        score += 1
        reasons.append("Fiyat SMA20 üzerinde")
    else:
        score -= 1
        reasons.append("Fiyat SMA20 altında")

    # 4) Trend (SMA20 vs SMA50)
    if a["sma20"] > a["sma50"]:
        score += 1
        reasons.append("SMA20 > SMA50 (yükseliş trendi)")
    else:
        score -= 1
        reasons.append("SMA20 < SMA50 (düşüş trendi)")

    # 5) Bollinger
    if price <= a["bb_lower"]:
        score += 1
        reasons.append("Fiyat alt Bollinger bandında (aşırı satım)")
    elif price >= a["bb_upper"]:
        score -= 1
        reasons.append("Fiyat üst Bollinger bandında (aşırı alım)")

    # 6) Hacim patlamasi
    vr = a.get("vol_ratio")
    if vr is not None and vr > 1.5:
        reasons.append(f"Hacim {vr:.1f}x arttı")
        score += 1 if score >= 0 else 0  # mevcut yonu destekler

    # Sinyal karari
    if score >= 5:
        signal, emoji = "GÜÇLÜ AL", "🟢"
    elif score >= 3:
        signal, emoji = "AL", "🟢"
    elif score >= 1:
        signal, emoji = "HAFİF AL", "🔵"
    elif score <= -5:
        signal, emoji = "GÜÇLÜ SAT", "🔴"
    elif score <= -3:
        signal, emoji = "SAT", "🔴"
    elif score <= -1:
        signal, emoji = "HAFİF SAT", "🟠"
    else:
        signal, emoji = "NÖTR", "⚪"

    # Stop-loss / hedef (ATR tabanli)
    atr_val = a["atr"] or price * 0.02
    if score >= 1:
        stop = price - 1.5 * atr_val
        target = price + 2.0 * atr_val
    else:
        stop = price + 1.5 * atr_val
        target = price - 2.0 * atr_val

    return {
        "symbol": sym,
        "score": score,
        "signal": signal,
        "emoji": emoji,
        "price": price,
        "rsi": a["rsi"],
        "trend": ind.trend_label(price, a["sma20"], a["sma50"]),
        "reasons": reasons,
        "stop": stop,
        "target": target,
        "atr": atr_val,
        "currency": md.currency_of(sym),
    }


def scan_symbols(symbols: list[str]) -> list[dict]:
    """Birden fazla sembolu tarar, guclu sinyale gore siralar."""
    results = []
    quotes = md.get_quotes_batch(symbols)
    for sym in symbols:
        sig = score_symbol(sym)
        if sig:
            q = quotes.get(sym)
            if q:
                sig["change_pct"] = q["change_pct"]
            results.append(sig)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
