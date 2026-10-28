"""Sinyal motoru.

Teknik gostergelerden puanlama ile kisa vadeli AL / SAT / NOTR sinyali uretir.
BILGI: Bu araclar yatirim tavsiyesi DEGILDIR. Sadece matematiksel gostergelerdir.
"""
from services import indicators as ind
from services import market_data as md


def score_from_analysis(a: dict) -> int:
    """Analiz sozlugunden ham puan hesaplar (backtest de bu kurali kullanir)."""
    score = 0
    r = a["rsi"]
    if r < 30:
        score += 2
    elif r < 40:
        score += 1
    elif r > 70:
        score -= 2
    elif r > 60:
        score -= 1

    if a["macd_hist"] > 0:
        score += 1
        if a["macd_hist"] > a["macd_hist_prev"]:
            score += 1
    else:
        score -= 1
        if a["macd_hist"] < a["macd_hist_prev"]:
            score -= 1

    if a["price"] > a["sma20"]:
        score += 1
    else:
        score -= 1

    if a["sma20"] > a["sma50"]:
        score += 1
    else:
        score -= 1

    if a["price"] <= a["bb_lower"]:
        score += 1
    elif a["price"] >= a["bb_upper"]:
        score -= 1

    vr = a.get("vol_ratio")
    if vr is not None and vr > 1.5:
        score += 1 if score >= 0 else 0
    return score


def signal_from_score(score: int) -> tuple[str, str]:
    """Puani sinyal + emojiye cevirir."""
    if score >= 5:
        return "GÜÇLÜ AL", "🟢"
    if score >= 3:
        return "AL", "🟢"
    if score >= 1:
        return "HAFİF AL", "🔵"
    if score <= -5:
        return "GÜÇLÜ SAT", "🔴"
    if score <= -3:
        return "SAT", "🔴"
    if score <= -1:
        return "HAFİF SAT", "🟠"
    return "NÖTR", "⚪"


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
    score = score_from_analysis(a)

    # Gerekceler
    r = a["rsi"]
    if r < 30:
        reasons.append(f"RSI {r:.0f} → aşırı satım, tepki alımı olası")
    elif r < 40:
        reasons.append(f"RSI {r:.0f} → zayıf, alım bölgesine yakın")
    elif r > 70:
        reasons.append(f"RSI {r:.0f} → aşırı alım, kar satışı riski")
    elif r > 60:
        reasons.append(f"RSI {r:.0f} → güçlü, satım bölgesine yakın")

    if a["macd_hist"] > 0:
        reasons.append("MACD pozitif ve güçleniyor" if a["macd_hist"] > a["macd_hist_prev"] else "MACD pozitif ama ivme kaybediyor")
    else:
        reasons.append("MACD negatif ve zayıflıyor" if a["macd_hist"] < a["macd_hist_prev"] else "MACD negatif ama toparlanıyor")

    reasons.append("Fiyat SMA20 üzerinde" if price > a["sma20"] else "Fiyat SMA20 altında")
    reasons.append("SMA20 > SMA50 (yükseliş trendi)" if a["sma20"] > a["sma50"] else "SMA20 < SMA50 (düşüş trendi)")

    if price <= a["bb_lower"]:
        reasons.append("Fiyat alt Bollinger bandında (aşırı satım)")
    elif price >= a["bb_upper"]:
        reasons.append("Fiyat üst Bollinger bandında (aşırı alım)")

    vr = a.get("vol_ratio")
    if vr is not None and vr > 1.5:
        reasons.append(f"Hacim {vr:.1f}x arttı")

    signal, emoji = signal_from_score(score)

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
