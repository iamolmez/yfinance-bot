"""Makro gosterge paneli: doviz, emtia ve endeksler tek ekranda."""
from services import market_data as md

SYMBOLS = [
    ("USD/TRY", "TRY=X"),
    ("EUR/TRY", "EURTRY=X"),
    ("EUR/USD", "EURUSD=X"),
    ("Altın (ons)", "GC=F"),
    ("Brent petrol", "BZ=F"),
    ("BIST 100", "XU100.IS"),
    ("S&P 500", "^GSPC"),
    ("Bitcoin", "BTC-USD"),
]


def dashboard() -> str:
    quotes = md.get_quotes_batch([s for _, s in SYMBOLS])
    lines = ["🌍 <b>Makro Piyasa Paneli</b>\n"]
    for label, sym in SYMBOLS:
        q = quotes.get(sym)
        if q:
            sign = "+" if q["change_pct"] >= 0 else ""
            emoji = "🟢" if q["change_pct"] >= 0 else "🔴"
            lines.append(
                f"{emoji} <b>{label}</b>: {q['price']:,.2f} ({sign}{q['change_pct']:.2f}%)"
            )
        else:
            lines.append(f"• {label}: veri yok")
    lines.append("\n⚠️ <i>Makro veriler bilgilendirme amaçlıdır.</i>")
    return "\n".join(lines)
