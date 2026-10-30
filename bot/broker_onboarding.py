"""Broker ayarlama sohbet akışı: /brokerayarla ile interaktif broker seçimi.

Akis:
  Soru 1: Broker seçimi (butonlar)
  -> Kaydedilir, gösterilir
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services import broker


ASK_BROKER = 0


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


async def start_broker_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broker ayarlama baslatir."""
    brokers_list = "\n".join([
        f"• <b>{b.name}</b> ({k})" for k, b in broker.BROKERS.items()
    ])
    kb = InlineKeyboardMarkup([
        [_btn("🏦 MİDAS", "broker_choice:midas")],
        [_btn("🏦 İŞ YATIRIM", "broker_choice:isyatirim")],
        [_btn("🏦 GARANTİ YATIRIM", "broker_choice:garanti")],
        [_btn("🏦 VAKIF YATIRIM", "broker_choice:vakif")],
        [_btn("🏦 DENİZ YATIRIM", "broker_choice:deniz")],
        [_btn("🆓 KOMİSYONSUZ (Sadece Spread)", "broker_choice:komisyonsuz_bist")],
        [_btn("🌍 INTERACTIVE BROKERS", "broker_choice:interactive_brokers")],
    ])
    await update.message.reply_text(
        f"🏛️ <b>Broker Seçimi</b>\n\n"
        f"Hangi broker'ı kullanıyorsun?\n\n{brokers_list}\n\n"
        f"Butondan seç ya da yaz: midas, isyatirim, garanti, vakif, deniz, komisyonsuz_bist, interactive_brokers\n\n"
        f"İptal: /vazgec",
        reply_markup=kb,
    )
    context.user_data["broker_setup"] = {}
    return ASK_BROKER


async def ask_broker_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buton secimi veya yazili cevap."""
    if update.callback_query:
        q = update.callback_query
        await q.answer()
        broker_key = q.data.split(":")[1]
    else:
        text = update.message.text.strip().lower()
        broker_key = text

    if broker_key not in broker.BROKERS:
        await update.message.reply_text(
            f"❌ Bilinmeyen broker: <code>{broker_key}</code>\n"
            f"Kullanılabilir: {', '.join(broker.BROKERS.keys())}"
        )
        return ASK_BROKER

    # Kaydet
    if await broker.set_user_broker(update.effective_user.id, broker_key):
        b = broker.BROKERS[broker_key]
        await update.message.reply_text(
            f"✅ Varsayılan broker: <b>{b.name}</b> ({broker_key})\n\n"
            f"Artık tüm maliyet hesaplamaları ({b.name} komisyonları ile) yapılacak."
        )
    else:
        await update.message.reply_text("❌ Kaydedilemedi, tekrar dene.")

    context.user_data.pop("broker_setup", None)
    return ConversationHandler.END


async def cancel_broker_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("broker_setup", None)
    await update.message.reply_text("🚫 Broker ayarlama iptal edildi.")
    return ConversationHandler.END


def broker_setup_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("brokerayarla", start_broker_setup)],
        states={
            ASK_BROKER: [
                CallbackQueryHandler(ask_broker_choice, pattern=r"^broker_choice:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_broker_choice),
            ],
        },
        fallbacks=[CommandHandler("vazgec", cancel_broker_setup)],
    )