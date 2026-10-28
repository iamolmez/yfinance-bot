"""Telegram Inline Query servisi.

Kullanici Telegram'da @botun THYAO yazinca anlik fiyat + mini grafik cikar.
Komut yazmana gerek kalmaz.
"""
from uuid import uuid4

from telegram import (
    InlineQueryResultArticle,
    InlineQueryResultPhoto,
    InputTextMessageContent,
)
from telegram.ext import InlineQueryHandler

from services import market_data as md
from services import charts


def parse_inline_query(text: str) -> list[str]:
    """Inline query metninden sembolleri cikarir.

    Ornek: "THYAO AAPL BTC" -> ["THYAO.IS", "AAPL", "BTC-USD"]
    """
    tokens = text.strip().upper().split()
    syms = []
    for t in tokens:
        resolved = md.resolve_symbol(t)
        if resolved:
            syms.append(resolved[0])
    return syms[:10]  # max 10 sonuc


async def inline_query_handler(update, context):
    """Inline query'yi isler."""
    query = update.inline_query.query.strip()
    if not query:
        return

    symbols = parse_inline_query(query)
    if not symbols:
        return

    results = []
    quotes = md.get_quotes_batch(symbols)

    for sym in symbols:
        q = quotes.get(sym)
        if not q:
            continue

        price = q["price"]
        change = q["change_pct"]
        cur = q["currency"]
        sign = "+" if change >= 0 else ""
        emoji = "🟢" if change >= 0 else "🔴"

        # Mini grafik (opsiyonel - performans icin kapali birakabiliriz)
        # img = charts.build_chart(sym, "1mo")

        title = f"{sym}: {price:,.2f} {cur} ({sign}{change:.2f}%)"
        description = f"{emoji} Günlük: {sign}{change:.2f}% | Hacim: {q['volume']:,.0f}"

        # Sonuc olarak mesaj gonderen article
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=title,
                description=description,
                input_message_content=InputTextMessageContent(
                    f"📊 <b>{sym}</b>\n"
                    f"💰 Fiyat: {q['price']:,.2f} {cur}\n"
                    f"📈 Günlük: {emoji} {sign}{change:.2f}%\n"
                    f"📅 Gün içi: {q['low']:,.2f} – {q['high']:,.2f} {cur}",
                    parse_mode="HTML",
                ),
            )
        )

    await update.inline_query.answer(results, cache_time=30, is_personal=True)


def register_inline_handler(app):
    """Inline query handler'i kaydeder."""
    app.add_handler(InlineQueryHandler(inline_query_handler))