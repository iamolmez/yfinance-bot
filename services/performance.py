"""Performans atfı: hangi karar ne kazandirdi?

- Pozisyon bazli getiri (gerceklesen + gerceklesmemis)
- Sektor/varlik sinifi bazli dagilim
- En iyi / en kotu kararlar
- Haftalik/aylik performans ozeti
"""
from collections import defaultdict

from database import get_transactions
from services import market_data as md
from services import portfolio


def calculate_position_returns(user_id: int) -> list[dict]:
    """Her pozisyon icin toplam getiri (gerceklesen + gerceklesmemis)."""
    pf = portfolio.get_portfolio(user_id)
    txns = get_transactions(user_id)

    # Sembol bazli alim maliyeti ve adet (FIFO)
    lots = {}
    for t in txns:
        if t["side"] == "BUY":
            lots.setdefault(t["symbol"], []).append({"qty": t["qty"], "price": t["price"]})
        else:
            # Satislarda FIFO'dan dus
            remaining = t["qty"]
            sym = t["symbol"]
            while remaining > 1e-9 and lots.get(sym):
                lot = lots[sym][0]
                take = min(remaining, lot["qty"])
                remaining -= take
                if take >= lot["qty"] - 1e-9:
                    lots[sym].pop(0)
                else:
                    lot["qty"] -= take

    out = []
    for p in pf["positions"]:
        sym = p.symbol
        mv = p.market_value
        cost = p.cost_basis
        unrealized = p.unrealized_pnl
        realized = p.realized_pnl
        total_return = realized + unrealized
        pct = (total_return / cost * 100) if cost else 0.0
        out.append({
            "symbol": sym,
            "market_value": mv,
            "cost_basis": cost,
            "realized": realized,
            "unrealized": unrealized,
            "total_return": total_return,
            "total_pct": pct,
            "qty": p.qty,
        })
    out.sort(key=lambda x: x["total_return"], reverse=True)
    return out


def attribution_text(user_id: int) -> str:
    """Performans atfi metni."""
    positions = calculate_position_returns(user_id)
    if not positions:
        return "📭 Portföy boş. /ekle ile alım yapın."

    total_mv = sum(p["market_value"] for p in positions)
    total_cost = sum(p["cost_basis"] for p in positions)
    total_return = sum(p["total_return"] for p in positions)
    total_pct = (total_return / total_cost * 100) if total_cost else 0.0

    lines = [
        "📈 <b>Performans Atfı</b>",
        f"🏦 Toplam: {total_mv:,.0f} ₺ (maliyet {total_cost:,.0f} ₺)",
        f"💰 Toplam K/Z: <b>{total_return:+,.0f} ₺ (%{total_pct:+.1f})</b>\n",
        "<b>🏆 En İyi 3 Karar:</b>",
    ]
    for i, p in enumerate(positions[:3], 1):
        lines.append(f"{i}. <b>{p['symbol']}</b>: {p['total_return']:+,.0f} ₺ (%{p['total_pct']:+.1f})")

    if len(positions) > 3:
        lines.append("\n<b>📉 En Zor 3 Karar:</b>")
        for i, p in enumerate(positions[-3:], len(positions) - 2):
            lines.append(f"{i}. <b>{p['symbol']}</b>: {p['total_return']:+,.0f} ₺ (%{p['total_pct']:+.1f})")

    # Varlik sinifi dagilimi
    from services import assistant
    class_mv = defaultdict(float)
    for p in positions:
        cls = assistant.classify_symbol(p["symbol"])
        class_mv[cls] += p["market_value"]

    lines.append("\n<b>🎯 Varlık Sınıfı Dağılımı:</b>")
    for cls, mv in sorted(class_mv.items(), key=lambda x: -x[1]):
        pct = mv / sum(class_mv.values()) * 100
        lines.append(f"• {assistant._CLASS_LABELS.get(cls, cls)}: {mv:,.0f} ₺ (%{pct:.0f})")

    lines.append("\n⚠️ <i>Geçmiş performans geleceği garanti etmez.</i>")
    return "\n".join(lines)


def weekly_performance(user_id: int) -> str:
    """Haftalik performans ozeti (Pazar 19:00 icin)."""
    from datetime import date, timedelta
    from services import portfolio

    pf = portfolio.get_portfolio(user_id)
    positions = pf["positions"]

    lines = ["📊 <b>Haftalık Performans</b>"]
    if not positions:
        lines.append("Portföy boş.")
        return "\n".join(lines)

    total_mv = sum(p.market_value for p in positions)
    lines.append(f"🏦 Portföy: {total_mv:,.0f} ₺ ({len(positions)} pozisyon)")

    # Basit: onceki hafta verisi yoksa sadece anlik gosterebiliriz
    lines.append("\n<i>Not: Haftalik getiri icin haftalik kapanis fiyatlari saklanmali.</i>")
    return "\n".join(lines)