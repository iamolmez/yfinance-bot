"""Kurumsal olay takvimi: temettü, çeyrek sonuçları, hisse bölünmesi, genel kurul.

Veri kaynagı: yfinance 'calendar' + manuel eklenebilir olaylar (corp_calendar tablosu).
"""
import datetime
from datetime import date, timedelta

import yfinance as yf

from database import add_corp_event, get_corp_calendar, get_corp_calendar_for_symbol
from services import market_data as md


# Sirket ismi -> yayin harici tum bilgi
_EVENT_TYPES = {
    "dividend": "💰 Temettü",
    "earnings": "📊 Çeyrek Sonuçları",
    "split": "✂️ Hisse Bölünmesi",
    "general_meeting": "🏛️ Genel Kurul",
    "ex_dividend": "📅 Temettü Hakkı Kesim (Ex-Dividend)",
}


def sync_calendar_for_symbol(sym: str, days_ahead: int = 60) -> int:
    """Bir sembol icin yfinance takvimini cekip corp_calendar'a senkronize eder.

    Dondurur: eklenen olay sayisi.
    """
    try:
        resolved = md.resolve_symbol(sym)
        if not resolved:
            return 0
        sym = resolved[0]
        cal = yf.Ticker(sym).calendar
    except Exception:
        return 0

    if cal is None or cal.empty:
        return 0

    added = 0
    end_date = date.today() + timedelta(days=days_ahead)

    for _, row in cal.iterrows():
        event_date = row.get("Date")
        if event_date is None:
            continue
        if hasattr(event_date, "date"):
            event_date = event_date.date()
        elif isinstance(event_date, str):
            try:
                event_date = datetime.date.fromisoformat(event_date[:10])
            except ValueError:
                continue
        if event_date > end_date:
            continue

        # Olay turunu tahmin et
        event_type = "earnings"
        if "Dividend" in str(row.get("Dividends", "")):
            event_type = "dividend"
        elif "Stock Split" in str(row.get("Stock Splits", "")):
            event_type = "split"

        try:
            add_corp_event(sym, event_type, event_date.isoformat(),
                          f"Yfinance: {event_type} tarihi {event_date}")
            added += 1
        except Exception:
            pass
    return added


def sync_all_watched(days_ahead: int = 60) -> int:
    """Takip listesindeki tum sembollerin takvimini senkronize eder."""
    from database import get_all_watchlists
    rows = get_all_watchlists()
    total = 0
    for r in rows:
        try:
            total += sync_calendar_for_symbol(r["symbol"], days_ahead)
        except Exception:
            pass
    return added


def format_calendar(events: list, days_ahead: int = 7) -> str:
    """Olaylari kullanici dostu metin olarak formatlar."""
    if not events:
        return "📭 Bu aralıkta planli kurumsal olay yok."

    today = date.today()
    end = today + timedelta(days=days_ahead)

    lines = [f"📅 <b>Kurumsal Takvim</b> (önümüzdeki {days_ahead} gün)\n"]

    by_date = {}
    for e in events:
        try:
            d = datetime.date.fromisoformat(e["event_date"][:10])
        except Exception:
            continue
        if d > end:
            continue
        by_date.setdefault(d, []).append(e)

    for d in sorted(by_date.keys()):
        label = d.strftime("%d %b %Y (%a)")
        lines.append(f"\n📌 <b>{label}</b>")
        for e in by_date[d]:
            icon = {
                "dividend": "💰",
                "earnings": "📊",
                "split": "✂️",
                "general_meeting": "🏛️",
                "ex_dividend": "📅",
            }.get(e["event_type"], "📌")
            det = e["details"] or ""
            lines.append(f"  {icon} <b>{e['symbol']}</b> — {_EVENT_TYPES.get(e['event_type'], e['event_type'])} {det}")

    if len(lines) == 1:
        return "📭 Bu aralıkta planli kurumsal olay yok."

    lines.append("\n⚠️ <i>Veri yfinance'tedir, gecikebilir/degisebilir. Resmi kaynaklari kontrol edin.</i>")
    return "\n".join(lines)


def get_upcoming_events(symbol: str | None = None, days: int = 7) -> list:
    """Manuel eklenen + yfinance olaylari birlestirip dondurur."""
    events = []
    if symbol:
        events.extend(get_corp_calendar_for_symbol(symbol))
    else:
        events.extend(get_corp_calendar(30))
    # Filtrele
    today = date.today()
    end = today + timedelta(days=days)
    out = []
    for e in events:
        try:
            d = datetime.date.fromisoformat(e["event_date"][:10])
            if today <= d <= end:
                out.append(e)
        except Exception:
            pass
    return out