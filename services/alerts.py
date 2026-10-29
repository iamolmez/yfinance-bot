"""Fiyat alarmi + ani hareket kontrol motoru."""
from datetime import date

from services import market_data as md
from services.webhooks import send_webhook, WebhookPayload

# (user_id, symbol) -> gun (ayni gun tekrar bildirilmez)
_last_big_move: dict[tuple, str] = {}


def check_all_alerts() -> list[dict]:
    """Aktif alarmlari kontrol eder. Tetiklenenleri dondurur.

    Her ogre: {"alert_id", "user_id", "symbol", "target", "direction",
               "current", "message"}
    """
    from database import deactivate_alert, get_alerts

    alerts = get_alerts(active_only=True)
    if not alerts:
        return []

    symbols = list({a["symbol"] for a in alerts})
    quotes = md.get_quotes_batch(symbols)

    triggered: list[dict] = []
    for a in alerts:
        q = quotes.get(a["symbol"])
        if not q:
            continue
        current = q["price"]
        target = a["target_price"]
        hit = (a["direction"] == "above" and current >= target) or (
            a["direction"] == "below" and current <= target
        )
        if hit:
            direction_tr = "üstüne çıktı" if a["direction"] == "above" else "altına indi"
            message = (
                f"🔔 ALARM: {a['symbol']} {direction_tr}!\n"
                f"🎯 Hedef: {target:,.2f} | Anlık: {current:,.2f} {q['currency']}"
            )
            alert_data = {
                "alert_id": a["id"],
                "user_id": a["user_id"],
                "symbol": a["symbol"],
                "target": target,
                "direction": a["direction"],
                "current": current,
                "message": message,
            }
            # Webhook gönder (varsa)
            webhook_url = a["webhook_url"] if "webhook_url" in a.keys() else ""
            webhook_type = a["webhook_type"] if "webhook_type" in a.keys() else ""
            if webhook_url and webhook_type:
                payload = WebhookPayload(
                    title="Fiyat Alarmı",
                    message=message,
                    symbol=a["symbol"],
                    price=current,
                    change_pct=q.get("change_pct"),
                    alert_type="price",
                )
                send_webhook(webhook_url, webhook_type, payload)
            triggered.append(alert_data)
            deactivate_alert(a["id"], a["user_id"])  # tek seferlik alarm
    return triggered


def check_big_moves(threshold_pct: float = 5.0) -> list[dict]:
    """Takip listesindeki varliklarda ani buyuk hareketleri bildirir.

    Ayni gun ayni varlik icin sadece bir kez bildirim yapilir.
    """
    from database import get_all_watchlists

    rows = get_all_watchlists()
    if not rows:
        return []

    by_user: dict[int, list[str]] = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r["symbol"])

    today = date.today().isoformat()
    out: list[dict] = []
    for user_id, symbols in by_user.items():
        quotes = md.get_quotes_batch(symbols)
        for sym, q in quotes.items():
            pct = q.get("change_pct")
            if pct is None or abs(pct) < threshold_pct:
                continue
            key = (user_id, sym)
            if _last_big_move.get(key) == today:
                continue
            _last_big_move[key] = today
            direction = "yükseldi 🚀" if pct > 0 else "düştü 📉"
            out.append(
                {
                    "user_id": user_id,
                    "symbol": sym,
                    "pct": pct,
                    "price": q["price"],
                    "currency": q["currency"],
                    "message": (
                        f"⚡ <b>Ani hareket:</b> {sym} bugün %{pct:+.2f} {direction}\n"
                        f"💵 Anlık: {q['price']:,.2f} {q['currency']}"
                    ),
                }
            )
    return out
