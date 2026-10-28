"""GVKY (Gelir Vergisi Beyannamesi) ve CSV Export.

Türkiye vergi mevzuatına uygun:
- FIFO maliyet bazlı satış kar/zararı
- Temettü gelirleri (kesintili / kesintisiz ayrımı)
- Yabancı hisse satış karı (yıllık 30.000 TL altı muaf)
- CSV export (muhasebeci/vergi dairesi formatında)
"""
import csv
import io
from datetime import date
from decimal import Decimal

from database import get_tax_events, get_dividend_events, get_transactions


def calculate_capital_gains(user_id: int, year: int) -> dict:
    """Yıllık sermaye kazancı/zararını hesaplar (FIFO).

    Türkiye kuralları:
    - BIST hisse: satış karı yearsizlik 30.000 TL'ye kadar muaf (2024: 30.000 TL)
    - Yabancı hisse: aynı muafiyet limiti
    - Komisyon/işlem maliyetleri maliyetten düşülür
    """
    from database import get_tax_events

    events = get_tax_events(user_id, year)
    if not events:
        return {"sales": [], "total_gain": 0, "taxable_gain": 0, "exempt_limit": 30000}

    # Sembol bazlı FIFO lotları
    lots = {}
    sales = []

    for e in events:
        sym = e["symbol"]
        if e["event_type"] == "buy":
            lots.setdefault(sym, []).append({
                "qty": e["qty"], "price": e["price"], "fee": e["fee"]
            })
        elif e["event_type"] == "sell":
            remaining = e["qty"]
            sell_price = e["price"]
            sell_fee = e["fee"]
            sell_date = e["event_date"]
            total_cost = 0.0
            total_qty = 0.0

            while remaining > 1e-9 and lots.get(sym):
                lot = lots[sym][0]
                take = min(remaining, lot["qty"])
                cost = take * lot["price"] + (lot["fee"] * take / lot["qty"])
                total_cost += cost
                total_qty += take
                remaining -= take
                if take >= lot["qty"] - 1e-9:
                    lots[sym].pop(0)
                else:
                    lot["qty"] -= take

            proceeds = total_qty * sell_price - sell_fee
            gain = proceeds - total_cost
            sales.append({
                "symbol": sym,
                "qty": total_qty,
                "buy_price": total_cost / total_qty if total_qty else 0,
                "sell_price": sell_price,
                "proceeds": proceeds,
                "cost_basis": total_cost,
                "gain": gain,
                "date": sell_date,
            })

    total_gain = sum(s["gain"] for s in sales)
    exempt_limit = 30000  # 2024 sınırı
    taxable_gain = max(total_gain - exempt_limit, 0)

    return {
        "sales": sales,
        "total_gain": total_gain,
        "exempt_limit": exempt_limit,
        "taxable_gain": taxable_gain,
    }


def calculate_dividend_income(user_id: int, year: int) -> dict:
    """Temettü gelirlerini hesaplar (kesintili / kesintisiz ayrımı)."""
    from database import get_dividend_events

    events = get_dividend_events(user_id, year=year)
    kesintili = 0.0
    kesintisiz = 0.0
    total_tax = 0.0

    for e in events:
        if e["tax_withheld"] > 0:
            kesintili += e["net_amount"]
            total_tax += e["tax_withheld"]
        else:
            kesintisiz += e["net_amount"]

    return {
        "events": events,
        "kesintili_toplam": kesintili,
        "kesintisiz_toplam": kesintisiz,
        "toplam_vergi": total_tax,
        "brut_toplam": kesintili + kesintisiz,
    }


def generate_gvky_report(user_id: int, year: int) -> dict:
    """GVKY için hazır rapor."""
    gains = calculate_capital_gains(user_id, year)
    divs = calculate_dividend_income(user_id, year)

    return {
        "year": year,
        "satislar": gains["sales"],
        "toplam_kazanc": gains["total_gain"],
        "muaf_limit": gains["exempt_limit"],
        "vergilendirilecek_kazanc": gains["taxable_gain"],
        "temettuler": divs["events"],
        "kesintili_temettu": divs["kesintili_toplam"],
        "kesintisiz_temettu": divs["kesintisiz_toplam"],
        "toplam_vergisi": divs["toplam_vergi"],
    }


def export_csv_transactions(user_id: int, year: int | None = None) -> str:
    """İşlemleri CSV olarak export eder (muhasebeci formatında)."""
    txns = get_transactions(user_id)
    if year:
        txns = [t for t in txns if t["created_at"].startswith(str(year))]

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "Tarih", "Sembol", "İşlem", "Adet", "Fiyat", "Tutar", "Komisyon",
        "Para Birimi", "Not"
    ])
    for t in txns:
        writer.writerow([
            t["created_at"][:10], t["symbol"], t["side"], t["qty"],
            f"{t['price']:.4f}", f"{t['qty'] * t['price']:.2f}",
            f"{t.get('fee', 0):.2f}", t["currency"], t.get("note", "")
        ])
    return output.getvalue()


def export_csv_portfolio(user_id: int) -> str:
    """Portföy pozisyonlarını CSV olarak export eder."""
    from services import portfolio
    pf = portfolio.get_portfolio(user_id)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "Sembol", "Adet", "Ortalama Maliyet", "Güncel Fiyat",
        "Piyasa Değeri", "Maliyet", "K/Z", "K/Z %", "Para Birimi"
    ])
    for p in pf["positions"]:
        writer.writerow([
            p.symbol, p.qty, f"{p.avg_cost:.4f}", f"{p.current_price:.4f}",
            f"{p.market_value:.2f}", f"{p.cost_basis:.2f}",
            f"{p.unrealized_pnl:.2f}", f"{p.unrealized_pct:.2f}",
            p.currency
        ])
    return output.getvalue()


def export_csv_dividends(user_id: int, year: int | None = None) -> str:
    """Temettüleri CSV olarak export eder."""
    events = get_dividend_events(user_id, year=year)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "Tarih (Ex)", "Ödeme Tarihi", "Sembol", "Brüt", "Vergi", "Net",
        "Para Birimi", "DRIP"
    ])
    for e in get_dividend_events(user_id, year=year):
        writer.writerow([
            e["ex_date"][:10], e["pay_date"] or "", e["symbol"],
            f"{e['gross_amount']:.2f}", f"{e['tax_withheld']:.2f}",
            f"{e['net_amount']:.2f}", e["currency"],
            "Evet" if e["drip_enabled"] else "Hayır"
        ])
    return output.getvalue()