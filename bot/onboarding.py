"""Onboarding akisi: /basla ile 5 soruluk kisisel plan kurulumu.

Akis:
  Soru 1: Maas      -> ASK_SALARY
  Soru 2: Gider     -> ASK_EXPENSES
  Soru 3: Risk      -> ASK_RISK   (butonlar)
  Soru 4: Hedef     -> ASK_GOAL   (butonlar)
  Soru 5: Maas gunu -> ASK_DAY    (butonlar)
  -> Plan olusturulur, kaydedilir, gosterilir
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

from bot.handlers import parse_number
from database import get_user_plan, set_user_plan
from services import assistant

ASK_SALARY, ASK_EXPENSES, ASK_RISK, ASK_GOAL, ASK_DAY = range(5)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = get_user_plan(update.effective_user.id)
    if existing:
        await update.message.reply_text(
            "🔄 Planın zaten var, yeniden kuruyorum. İptal için /vazgec\n\n"
        )
    await update.message.reply_text(
        "🧭 <b>Kişisel Asistan Kurulumu</b>\n\n"
        "Birkaç soruyla maaşını otomatik bölen, sana özel bir plan çıkaracağım. "
        "5 kısa soru, ~2 dakika. İptal: /vazgec\n\n"
        "💵 <b>Soru 1/5:</b> Aylık maaşın ne kadar? (₺)\n"
        "Örn: <code>50000</code>"
    )
    context.user_data["onboarding"] = {}
    return ASK_SALARY


async def ask_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_number(update.message.text)
    if val is None or val <= 0:
        await update.message.reply_text("❌ Lütfen sayı girin. Örn: <code>50000</code>")
        return ASK_SALARY
    context.user_data["onboarding"]["salary"] = val
    await update.message.reply_text(
        f"✅ Maaş: <b>{val:,.2f} ₺</b>\n\n"
        "💸 <b>Soru 2/5:</b> Aylık zorunlu giderlerin yaklaşık ne kadar? "
        "(kira, faturalar, mutfak, ulaşım, taksitler...)\n"
        "Örn: <code>25000</code>"
    )
    return ASK_EXPENSES


async def ask_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_number(update.message.text)
    if val is None or val < 0:
        await update.message.reply_text("❌ Lütfen sayı girin. Örn: <code>25000</code>")
        return ASK_EXPENSES
    context.user_data["onboarding"]["expenses"] = val
    kb = InlineKeyboardMarkup(
        [
            [_btn("🛡️ Sakin — kayıptan korkarım, uyuyamam", "risk:sakin")],
            [_btn("⚖️ Dengeli — biraz dalgalanma kabul ederim", "risk:dengeli")],
            [_btn("🚀 Atılgan — yüksek dalgalanma kabul ederim", "risk:atilgan")],
        ]
    )
    await update.message.reply_text(
        "🧠 <b>Soru 3/5: Risk anlayışın hangisine yakın?</b>\n\n"
        "• <b>Sakin:</b> Paramı kaybetmekten çok korkarım, düşük riskli araçlar isterim\n"
        "• <b>Dengeli:</b> Biraz iniş çıkış kabul edebilirim, uzun vade düşünürüm\n"
        "• <b>Atılgan:</b> Dalgalanmayı kabul ederim, daha çok kazanmak isterim",
        reply_markup=kb,
    )
    return ASK_RISK


async def ask_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["onboarding"]["risk"] = q.data.split(":")[1]
    kb = InlineKeyboardMarkup(
        [
            [_btn("🆘 Acil durum fonu (önce güvenlik)", "goal:acil_fon")],
            [_btn("🏠 Ev / araba / büyük hedef", "goal:buyuk_hedef")],
            [_btn("👵 Emeklilik / uzun vade", "goal:emeklilik")],
            [_btn("⚡ Kısa vadede kazanç", "goal:kisa_vade")],
        ]
    )
    await q.edit_message_text(
        "🎯 <b>Soru 4/5: Bu para senin için ne amaçlı?</b>\n\n"
        "En önemli amacını seç, planı ona göre kurarım:",
        reply_markup=kb,
    )
    return ASK_GOAL


async def ask_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["onboarding"]["goal"] = q.data.split(":")[1]
    kb = InlineKeyboardMarkup(
        [
            [_btn("1", "day:1"), _btn("5", "day:5"), _btn("10", "day:10")],
            [_btn("15", "day:15"), _btn("20", "day:20"), _btn("25", "day:25")],
            [_btn("Ay sonu (30/31)", "day:30")],
        ]
    )
    await q.edit_message_text(
        "📆 <b>Soru 5/5: Maaşını ayın kaçında alıyorsun?</b>\n\n"
        "Maaş gününde sana dağılımı hatırlatırım:",
        reply_markup=kb,
    )
    return ASK_DAY


async def ask_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = context.user_data.get("onboarding", {})
    day = int(q.data.split(":")[1])
    try:
        plan = assistant.build_plan(
            data["salary"], data["expenses"], data["risk"], data["goal"], day
        )
    except KeyError:
        await q.edit_message_text("❌ Kurulum yarıda kaldı, /basla ile tekrar başlayın.")
        return ConversationHandler.END

    set_user_plan(
        update.effective_user.id, plan["salary"], plan["expenses"],
        plan["risk"], plan["goal"], day, plan["emergency_target"],
        assistant.plan_to_json(plan),
    )
    context.user_data.pop("onboarding", None)

    welcome = (
        "🎉 <b>Planın hazır!</b>\n\n"
        + assistant.describe_plan(plan)
        + "\n\n"
        "🤖 <b>Bundan sonra ne olacak?</b>\n"
        "🌅 Her sabah sana hatırlatacağım\n"
        "🌙 Her akşam 'Bugün harcama yaptın mı?' diye soracağım\n"
        "🎉 Maaş gününde dağılımı hatırlatacağım\n"
        "💡 Arada bir basit finans bilgisi öğreteceğim\n\n"
        "Alışverişlerini kaydetmeyi unutma: /harcama TUTAR KATEGORİ"
    )
    await q.edit_message_text(welcome)
    return ConversationHandler.END


async def ask_press_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👇 Lütfen aşağıdaki butonlardan birini seç. (İptal: /vazgec)")
    return None  # mevcut state'te kal


async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("onboarding", None)
    await update.message.reply_text("🚫 Kurulum iptal edildi. Dilediğin zaman /basla ile yeniden başlayabilirsin.")
    return ConversationHandler.END


def onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("basla", start_onboarding)],
        states={
            ASK_SALARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_salary)
            ],
            ASK_EXPENSES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_expenses)
            ],
            ASK_RISK: [
                CallbackQueryHandler(ask_risk, pattern=r"^risk:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_press_button),
            ],
            ASK_GOAL: [
                CallbackQueryHandler(ask_goal, pattern=r"^goal:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_press_button),
            ],
            ASK_DAY: [
                CallbackQueryHandler(ask_day, pattern=r"^day:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_press_button),
            ],
        },
        fallbacks=[CommandHandler("vazgec", cancel_onboarding)],
    )
