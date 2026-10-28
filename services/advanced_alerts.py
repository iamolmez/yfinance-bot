"""Gelişmiş alarm motoru: RSI, MACD, Bollinger, Hacim, Fiyat seviyesi.

Kullanici: /alarm2 THYAO rsi 30 below
Bot: Her 15 dk'de bir kontrol eder, esik geildiginde bildirir.
"""
import json

from database import (
    add_alert_config,
    deactivate_alert_config,
    get_alert_configs,
)
from services import market_data as md
from services import indicators as ind

_ALERT_TYPES = {
    "rsi": {"name": "RSI", "params": ["threshold", "direction"]},
    "macd": {"name": "MACD", "params": ["direction"]},
    "bb": {"name": "Bollinger Bands", "params": ["band", "direction"]},
    "volume": {"name": "Hacim", "params": ["multiplier"]},
    "price": {"name": "Fiyat", "params": ["target", "direction"]},
}

_ALERT_DIRS = {
    "above": "üstüne çıkınca",
    "below": "altına inince",
    "cross_up": "yukarı kesince",
    "cross_down": "aşağı kesince",
    "expand": "genişlerken",
    "squeeze": "daralirken",
}


def validate_alert_config(type_: str, params: dict) -> tuple[bool, str]:
    """Parametreleri dogrular."""
    if type_ not in _ALERT_TYPES:
        return False, f"Desteklenmeyen alarm turu: {type_}. Kullanilabilir: {', '.join(_ALERT_TYPES.keys())}"
    required = _ALERT_TYPES[type_]["params"]
    for r in required:
        if r not in params:
            return False, f"Eksik parametre: {r}. Gerekli: {required}"
    return True, ""


def create_alert(user_id: int, symbol: str, type_: str, params: dict) -> int | None:
    """Alarm olusturur. Basarili olursa config_id dondurur."""
    ok, msg = validate_alert_config(type_, params)
    if not ok:
        return None
    config_id = add_alert_config(
        user_id, symbol, type_, json.dumps(params, ensure_ascii=False)
    )
    return config_id


def check_advanced_alerts() -> list[dict]:
    """Tum aktif gelismis alarmlari kontrol eder, tetiklenenleri dondurur.

    Her ogre: {"config_id", "user_id", "symbol", "type", "message", "current_value"}
    """
    configs = get_alert_configs(None, active_only=True)
    if not configs:
        return []

    symbols = list({c["symbol"] for c in configs})
    quotes = md.get_quotes_batch(symbols)

    # Her sembol icin df cek (gostergeler icin)
    dfs = {}
    for sym in symbols:
        df = md.get_history(sym, period="3mo")
        if df is not None and not df.empty:
            dfs[sym] = df

    triggered = []
    for c in configs:
        sym = c["symbol"]
        type_ = c["type"]
        params = json.loads(c["params"]) if c["params"] else {}
        q = quotes.get(sym)
        if not q:
            continue

        df = dfs.get(sym)
        hit = False
        current = None
        msg = ""

        if type_ == "rsi":
            if df is None or df.empty:
                continue
            r = ind.rsi(df["Close"])
            current = float(r.iloc[-1])
            threshold = params["threshold"]
            direction = params["direction"]
            if direction == "below" and current <= threshold:
                hit = True
            elif direction == "above" and current >= threshold:
                hit = True
            msg = f"RSI {current:.1f} {_ALERT_DIRS.get(direction, direction)} ({threshold})"

        elif type_ == "macd":
            if df is None or df.empty:
                continue
            macd_line, sig_line, hist = ind.macd(df["Close"])
            h = float(hist.iloc[-1])
            h_prev = float(hist.iloc[-2]) if len(hist) > 1 else h
            direction = params["direction"]
            if direction == "cross_up" and h_prev <= 0 and h > 0:
                hit = True
            elif direction == "cross_down" and h_prev >= 0 and h < 0:
                hit = True
            msg = f"MACD histogram {_ALERT_DIRS.get(direction, direction)} (hist: {h:.2f})"

        elif type_ == "bb":
            if df is None or df.empty:
                continue
            bb_up, bb_mid, bb_lo = ind.bollinger(df["Close"])
            price = q["price"]
            band = params["band"]  # upper, lower, mid
            direction = params["direction"]
            bb_val = {"upper": float(bb_up.iloc[-1]), "lower": float(bb_lo.iloc[-1]),
                      "mid": float(bb_mid.iloc[-1])}[band]
            current = price
            if direction == "above" and price >= bb_val:
                hit = True
            elif direction == "below" and price <= bb_val:
                hit = True
            msg = f"Fiyat {price:.2f} Bollinger {band} bandini {_ALERT_DIRS.get(direction, direction)} ({bb_val:.2f})"

        elif type_ == "volume":
            if df is None or df.empty or "Volume" not in df.columns:
                continue
            vol = df["Volume"].dropna()
            if len(vol) < 2:
                continue
            current = float(vol.iloc[-1])
            avg = float(vol.iloc[-20:].mean())
            mult = params["multiplier"]
            if current >= avg * mult:
                hit = True
                msg = f"Hacim {current:,.0f} = {current/avg:.1f}x ortalama (esik: {mult}x)"

        elif type_ == "price":
            current = q["price"]
            target = params["target"]
            direction = params["direction"]
            if direction == "above" and current >= target:
                hit = True
            elif direction == "below" and current <= target:
                hit = True
            msg = f"Fiyat {current:.2f} hedef {target:.2f}'i {_ALERT_DIRS.get(direction, direction)}"

        if hit:
            deactivate_alert_config(c["id"], c["user_id"])
            triggered.append({
                "config_id": c["id"],
                "user_id": c["user_id"],
                "symbol": c["symbol"],
                "type": c["type"],
                "message": f"🔔 <b>{_ALERT_TYPES[type_]['name']} Alarmı:</b> {c['symbol']} — {msg}",
                "current_value": current,
            })
    return triggered


def format_alert_help() -> str:
    return (
        "🔔 <b>Gelişmiş Alarm Türleri</b>\n\n"
        "<b>/alarm2 SYMBOL TÜR PARAMETRELER</b>\n\n"
        "📉 <b>RSI:</b> <code>/alarm2 THYAO rsi 30 below</code>\n"
        "   RSI 30'un altına inince\n"
        "   Parametreler: threshold (sayi), direction (above/below)\n\n"
        "📊 <b>MACD:</b> <code>/alarm2 THYAO macd cross_up</code>\n"
        "   MACD histogram 0'u yukarı/aşağı kesince\n"
        "   Parametreler: direction (cross_up/cross_down)\n\n"
        "📏 <b>Bollinger:</b> <code>/alarm2 THYAO bb upper above</code>\n"
        "   Fiyat Bollinger bandini geçince\n"
        "   Parametreler: band (upper/lower/mid), direction (above/below)\n\n"
        "📦 <b>Hacim:</b> <code>/alarm2 THYAO volume 2</code>\n"
        "   Hacim ortalamanın N katı olunca\n"
        "   Parametreler: multiplier (sayi)\n\n"
        "💰 <b>Fiyat:</b> <code>/alarm2 THYAO price 300 above</code>\n"
        "   Basit fiyat alarmı (eski /alarm ile ayni)\n"
        "   Parametreler: target (sayi), direction (above/below)\n\n"
        "📋 <b>Aktif alarmlar:</b> /alarm2lar\n"
        "🗑️ <b>Sil:</b> /alarm2sil ID"
    )