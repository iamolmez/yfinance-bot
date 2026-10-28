"""Temettü (Dividend) takibi ve DRIP (Dividend Reinvestment Plan) yönetimi.

- Temettü takibi: brüt, vergi, net, ex-date, pay-date
- DRIP: Temettüyü otomatik yeniden yatırım önerisi
- Temettü getirisi (yield) takibi
"""
from datetime import date
from collections import defaultdict

from database import (
    add_dividend_event, get_dividend_events, get_dividend_events,
)
from services import market_data as md, portfolio


def add_dividend(user_id: int, symbol: str, gross: float, tax: float,
                 currency: str, ex_date: str, pay_date: str | None = None,
                 drip: bool = False) -> int:
    """Temettü kaydı ekler."""
    net = gross - tax
    pay = pay_date or ""
    return add_dividend_event(user_id, symbol, gross, tax, gross - tax,
                              currency, ex_date, pay, int(drip))


def get_dividend_summary(user_id: int, year: int | None = None) -> dict:
    """Yıllık temettü özeti."""
    events = get_dividend_events(user_id, year=year)

    total_gross = sum(e["gross_amount"] for e in events)
    total_tax = sum(e["tax_withheld"] for e in events)
    total_net = sum(e["net_amount"] for e in events)
    drip_events = [e for e in events if e["drip_enabled"]]

    by_symbol = defaultdict(lambda: {"gross": 0, "tax": 0, "net": 0, "count": 0})
    for e in events:
        s = by_symbol[e["symbol"]]
        s["gross"] += e["gross_amount"]
        s["tax"] += e["tax_withheld"]
        s["net"] += e["net_amount"]
        s["count"] += 1

    return {
        "year": year or date.today().year,
        "total_gross": total_gross,
        "total_tax": total_tax,
        "total_net": total_net,
        "count": len(events),
        "drip_count": len(drip_events),
        "by_symbol": dict(by_symbol),
    }


def get_dividend_yield(user_id: int, symbol: str) -> float | None:
    """Bir hisse için temettü getirisi (yield) hesaplar.

    Son 12 ay temettüleri / güncel fiyat.
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=365)
    events = get_dividend_events(user_id, symbol=symbol)

    total_div = sum(
        e["net_amount"] for e in events
        if date.fromisoformat(e["ex_date"][:10]) >= start
    )

    if total_div <= 0:
        return None

    df = md.get_history(symbol, period="5d")
    if df is None or df.empty:
        return None

    price = float(df["Close"].iloc[-1])
    return (total_div / price) * 100


def drip_suggestions(user_id: int, min_amount: float = 100.0) -> list[dict]:
    """DRIP (yeniden yatırım) önerileri.

    Temettü net tutarı min_amount'ın üzerindeyse ve DRIP aktifse,
    aynı hisseyi tekrar alma önerisi.
    """
    events = get_dividend_events(user_id)
    suggestions = []

    for e in events:
        if e["drip_enabled"] and e["net_amount"] >= min_amount:
            suggestions.append({
                "symbol": e["symbol"],
                "amount": e["net_amount"],
                "date": e["ex_date"],
                "note": f"Temettü {e['net_amount']:.2f} {e['currency']} — aynı hisseyi yeniden alabilirsiniz"
            })

    return suggestions


def dividend_income_forecast(user_id: int, months: int = 12) -> dict:
    """Gelecek aylar için temettü tahmini (geçmiş verilere dayalı)."""
    from datetime import date, timedelta

    today = date.today()
    end = today + timedelta(days=30 * months)

    events = get_dividend_events(user_id)

    # Sembol bazlı ortalama temettü sıklığı ve tutarını hesapla
    symbol_divs = defaultdict(list)
    for e in get_dividend_events(user_id):
        d = date.fromisoformat(e["ex_date"][:10])
        symbol_divs[e["symbol"]].append((d, e["net_amount"]))

    forecast = {}
    for sym, divs in symbol_divs.items():
        if len(divs) >= 2:
            # Ortalama aralık ve tutar
            dates = sorted([d for d, _ in divs])
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            avg_interval = sum(intervals) / len(intervals) if intervals else 90
            avg_amount = sum(a for _, a in divs) / len(divs)

            # Son temettüden itibaren geleceğini tahmin et
            last_date = dates[-1]
            next_date = last_date + timedelta(days=avg_interval)
            while next_date <= end:
                forecast.setdefault(next_date.isoformat(), []).append({
                    "symbol": sym,
                    "estimated": avg_amount,
                })
                next_date += timedelta(days=avg_interval)

    return {
        "period_months": months,
        "forecast": dict(sorted(forecast.items())),
        "disclaimer": "Geçmiş verilere dayalı tahmindir, garantili değildir."
    }


def dividend_text(summary: dict) -> str:
    lines = [
        f"💰 <b>Temettü Özeti ({summary['year']})</b>",
        f"💰 Toplam Brüt: {summary['total_gross']:,.2f} ₺",
        f"💸 Toplam Vergi: {summary['total_tax']:,.2f} ₺",
        f"💰 Toplam Net: <b>{summary['total_net']:,.2f} ₺</b>",
        f"📋 Kayıt Sayısı: {summary['count']} ({summary['drip_count']} DRIP)",
        "",
        "<b>📊 Sembol Bazında:</b>",
    ]
    for sym, data in sorted(summary["by_symbol"].items(), key=lambda x: -x[1]["net"]):
        lines.append(f"• {sym}: Net {data['net']:,.2f} ₺ ({data['count']} ödeme)")

    if summary["drip_count"] > 0:
        lines.append(f"\n🔄 DRIP Aktif: {summary['drip_count']} ödeme otomatik yeniden yatırım için işaretli")

    return "\n".join(lines)