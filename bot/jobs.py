"""Arka plan gorevleri (JobQueue).

1. check_alerts_job    : fiyat alarmlarini kontrol eder (her 3 dk)
2. signal_digest_job   : takip listesini tarar, guclu sinyalleri bildirir (saatlik)
3. daily_summary_job   : aksamlari portfoy + sinyal ozeti gonderir (18:30)
4. morning_checkin_job : sabahlari asistan mesaji (09:00) - hatirlatma + tip + ozet
5. evening_checkin_job : aksamlari harcama kontrolu (20:00) - butonlu soru
6. salary_day_job      : maas gununde dagilim hatirlatmasi (09:30)
"""
import asyncio
import logging
from datetime import datetime, time as dtime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import config
from database import (
    get_all_watchlists,
    get_cash,
    get_user_plan,
    get_watchlist,
    query,
)
from services import alerts as alert_svc
from services import assistant, budget, market_data as md, picker, portfolio, signals
from services.market_data import TZ_ISTANBUL

logger = logging.getLogger(__name__)


async def to_thread(fn, *args):
    return await asyncio.to_thread(fn, *args)


def _first_name(user_id: int) -> str:
    row = query("SELECT first_name FROM users WHERE user_id = ?", (user_id,))
    return (row[0]["first_name"] or "arkadaşım") if row else "arkadaşım"


async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    # Fiyat alarmlari + ani buyuk hareketler birlikte kontrol edilir
    triggered = await to_thread(alert_svc.check_all_alerts)
    big = await to_thread(alert_svc.check_big_moves, config.BIG_MOVE_PCT)
    for t in triggered + big:
        try:
            await context.bot.send_message(chat_id=t["user_id"], text=t["message"])
        except Exception as e:  # kullanici botu engellemis olabilir
            logger.warning("Alarm gonderilemedi (%s): %s", t["user_id"], e)


async def _watch_summary(user_id: int, top: int = 3) -> list[str]:
    watch = get_watchlist(user_id)
    if not watch:
        return []
    symbols = [w["symbol"] for w in watch]
    quotes = await to_thread(md.get_quotes_batch, symbols)
    items = sorted(
        quotes.values(), key=lambda q: abs(q["change_pct"]), reverse=True
    )[:top]
    lines = []
    for q in items:
        sign = "+" if q["change_pct"] >= 0 else ""
        emoji = "🟢" if q["change_pct"] >= 0 else "🔴"
        lines.append(f"{emoji} {q['symbol']}: {q['price']:,.2f} ({sign}{q['change_pct']:.2f}%)")
    return lines


async def morning_checkin_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ_ISTANBUL)
    for user_id in config.ALLOWED_USER_IDS:
        try:
            name = _first_name(user_id)
            plan_row = get_user_plan(user_id)
            plan = assistant.plan_from_json(plan_row["plan"]) if plan_row else None
            saved = plan_row["emergency_saved"] or 0 if plan_row else 0

            lines = [
                f"🌅 <b>Günaydın {name}!</b>",
                f"📅 {now:%A, %d %B %Y}",
                "",
            ]
            summary = await _watch_summary(user_id)
            if summary:
                lines += ["<b>📊 Piyasa (takip listen)</b>"] + summary + [""]
            else:
                lines += ["💡 Piyasa takibi için: <code>/takip SYMBOL</code> (örn: /takip THYAO)", ""]

            if plan:
                rep = budget.get_month_report(user_id)
                lines.append(assistant.today_action(plan, saved, rep["invested"], rep["invest_target"]))
                lines.append("")
                lines.append(assistant.emergency_status(plan, saved))
                if summary:
                    # en guclu sinyali sade dille anlat
                    symbols = [w["symbol"] for w in get_watchlist(user_id)]
                    if symbols:
                        results = await to_thread(signals.scan_symbols, symbols)
                        if results and results[0]["score"] >= 1:
                            lines.append("")
                            lines.append(assistant.simple_signal_hint(results[0]))
            else:
                lines.append("📋 Henüz planın yok. 2 dakikada oluşturalım: <code>/basla</code>")

            lines += ["", f"💡 <b>Bilgi:</b> {assistant.tip_of_day()}"]
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Sabah mesaji gonderilemedi (%s): %s", user_id, e)


async def evening_checkin_job(context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💸 Evet, harcama yaptım", callback_data="checkin:expense:yes"),
                InlineKeyboardButton("✅ Hayır", callback_data="checkin:expense:no"),
            ]
        ]
    )
    for user_id in config.ALLOWED_USER_IDS:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🌙 <b>Akşam kontrolü</b>\n\nBugün harcama yaptın mı?",
                reply_markup=kb,
            )
        except Exception as e:
            logger.warning("Aksam kontrolu gonderilemedi (%s): %s", user_id, e)


async def salary_day_job(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(TZ_ISTANBUL).day
    for user_id in config.ALLOWED_USER_IDS:
        try:
            plan_row = get_user_plan(user_id)
            if not plan_row or plan_row["salary_day"] != today:
                continue
            plan = assistant.plan_from_json(plan_row["plan"])
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ Maaşımı aldım, ayı başlat", callback_data="salary:received")]]
            )
            lines = [
                "🎉 <b>Maaş günün kutlu olsun!</b>",
                "",
                "Planına göre bu ayın dağılımı:",
                f"🏠 Zorunlu giderler: {plan['needs']:,.2f} ₺",
                f"🎉 İsteğe bağlı: {plan['wants']:,.2f} ₺",
                f"💾 Birikim: {plan['savings']:,.2f} ₺",
                f"   ├ 🛡️ Acil fon: {plan['emergency_share']:,.2f} ₺",
                f"   └ 📈 Yatırım: {plan['invest_share']:,.2f} ₺",
                "",
                "Maaşını aldıysan aşağıdan onayla, yeni ayı başlatalım:",
            ]
            await context.bot.send_message(
                chat_id=user_id, text="\n".join(lines), reply_markup=kb
            )
        except Exception as e:
            logger.warning("Maas gunu mesaji gonderilemedi (%s): %s", user_id, e)


async def signal_digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Her kullanici icin takip listesini tara, sadece islem sinyali verenleri bildir."""
    rows = get_all_watchlists()
    by_user: dict[int, list[str]] = {}
    for r in rows:
        by_user.setdefault(r["user_id"], []).append(r["symbol"])

    for user_id, symbols in by_user.items():
        if user_id not in config.ALLOWED_USER_IDS:
            continue
        try:
            results = await to_thread(signals.scan_symbols, symbols)
        except Exception as e:
            logger.warning("Tarama hatasi (%s): %s", user_id, e)
            continue
        actionable = [r for r in results if abs(r["score"]) >= 3]
        if not actionable:
            continue
        lines = ["🔔 <b>Saatlik Sinyal Taraması</b>\n"]
        for r in actionable:
            lines.append(
                f"{r['emoji']} <b>{r['symbol']}</b> — {r['signal']} "
                f"(skor {r['score']:+d}, {fmt(r['price'], r['currency'])})"
            )
        lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
        try:
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Sinyal gonderilemedi (%s): %s", user_id, e)


async def session_open_job(context: ContextTypes.DEFAULT_TYPE):
    """BIST seansi acildi (hafta ici 10:05): takip listesi hareketleri."""
    for user_id in config.ALLOWED_USER_IDS:
        try:
            summary = await _watch_summary(user_id, top=5)
            if not summary:
                continue
            lines = [
                "🇹🇷 <b>BIST Seansı Açıldı</b>",
                f"🕐 {datetime.now(TZ_ISTANBUL):%H:%M} (TR)",
                "",
                "<b>📊 Takip listen (günlük değişim)</b>",
            ] + summary
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Seans acilis mesaji gonderilemedi (%s): %s", user_id, e)


async def invest_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Ayin 15'i ve 28'i: yatirim hedefi hatirlatmasi."""
    today = datetime.now(TZ_ISTANBUL)
    if today.day not in (15, 28):
        return
    for user_id in config.ALLOWED_USER_IDS:
        try:
            plan_row = get_user_plan(user_id)
            if not plan_row:
                continue
            plan = assistant.plan_from_json(plan_row["plan"])
            if plan["invest_share"] <= 0:
                continue
            rep = budget.get_month_report(user_id)
            remaining = max(plan["invest_share"] - rep["invested"], 0)
            lines = [f"📈 <b>Yatırım Hatırlatması</b> ({today.day}. gün)"]
            if remaining > 0:
                lines += [
                    "",
                    f"Bu ay yatırım hedefin: <b>{plan['invest_share']:,.2f} ₺</b>",
                    f"Şu ana kadar: {rep['invested']:,.2f} ₺",
                    f"⏳ Kalan: <b>{remaining:,.2f} ₺</b>",
                    "",
                    "Fırsatları görmek için: /sinyal",
                    "İşlem kaydetmek için: /ekle SYMBOL ADET FIYAT",
                ]
            else:
                lines += ["", "🎉 Bu ayın yatırım hedefini tamamladın. Tebrikler!"]
            lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Yatirim hatirlatmasi gonderilemedi (%s): %s", user_id, e)


async def weekly_report_job(context: ContextTypes.DEFAULT_TYPE):
    """Pazar 19:00: haftalik ozet."""
    from datetime import timedelta

    now = datetime.now(TZ_ISTANBUL)
    week_start = (now - timedelta(days=now.weekday() + 1)).date().isoformat()  # pazartesi
    for user_id in config.ALLOWED_USER_IDS:
        try:
            plan_row = get_user_plan(user_id)
            rep = budget.get_month_report(user_id)
            pf = await to_thread(portfolio.get_portfolio, user_id)

            lines = [
                "📑 <b>Haftalık Rapor</b>",
                f"🗓️ {week_start} – {now:%d.%m.%Y}",
                "",
                "<b>💰 Bu Hafta</b>",
                f"• Harcama: {rep['total_expense']:,.2f} ₺ (bu ay)",
                f"• Yatırım: {rep['invested']:,.2f} / {rep['invest_target']:,.2f} ₺ (%{rep['invest_pct']:.0f})",
                f"• Kalan: {rep['remaining']:,.2f} ₺",
            ]
            if pf["positions"]:
                lines += ["", "<b>💼 Portföy</b>"]
                for p in pf["positions"][:6]:
                    arrow = "🟢" if p.unrealized_pnl >= 0 else "🔴"
                    lines.append(f"• {arrow} {p.symbol}: {p.market_value:,.2f} ({p.unrealized_pnl:+,.2f})")
            if plan_row:
                plan = assistant.plan_from_json(plan_row["plan"])
                lines += ["", assistant.emergency_status(plan, plan_row["emergency_saved"] or 0)]
            lines += [
                "",
                f"💡 <b>Haftanın Bilgisi:</b> {assistant.tip_of_day()}",
                "",
                "Haftaya planlı başla: /asistan",
            ]
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Haftalik rapor gonderilemedi (%s): %s", user_id, e)


async def auto_pick_job(context: ContextTypes.DEFAULT_TYPE):
    """Her gun 15:00: plani olan kullanicilara otomatik alim onerileri."""
    for user_id in config.ALLOWED_USER_IDS:
        try:
            plan_row = get_user_plan(user_id)
            if not plan_row:
                continue
            plan = assistant.plan_from_json(plan_row["plan"])
            if plan.get("invest_share", 0) <= 0:
                continue
            pf = await to_thread(portfolio.get_portfolio, user_id)
            cash = await to_thread(get_cash, user_id)
            result = await to_thread(picker.pick, plan, pf["positions"], cash)
            if not result["safe"] and not result["risky"]:
                continue  # bugun firsat yoksa rahatsiz etme
            msg = (
                "🕒 <b>Günlük Otomatik Seçim</b>\n"
                + picker.pick_message(result)
            )
            await context.bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logger.warning("Otomatik secim gonderilemedi (%s): %s", user_id, e)


async def stop_loss_job(context: ContextTypes.DEFAULT_TYPE):
    """Pozisyonlari stop-loss esigiyle kontrol eder, gunluk bir kez uyarir."""
    pct = config.STOP_LOSS_PCT
    today = datetime.now(TZ_ISTANBUL).date().isoformat()
    for user_id in config.ALLOWED_USER_IDS:
        try:
            pf = await to_thread(portfolio.get_portfolio, user_id)
            for p in pf["positions"]:
                if not p.avg_cost:
                    continue
                stop = p.avg_cost * (1 - pct / 100)
                if p.current_price <= stop:
                    key = (user_id, p.symbol)
                    if _last_stop_notify.get(key) == today:
                        continue
                    _last_stop_notify[key] = today
                    drop = (p.current_price / p.avg_cost - 1) * 100
                    msg = (
                        f"⚠️ <b>Stop-loss uyarısı: {p.symbol}</b>\n"
                        f"💰 Maliyet: {p.avg_cost:,.2f} | Anlık: {p.current_price:,.2f} ({drop:+.1f}%)\n"
                        f"🛑 Zarar kes seviyen: {stop:,.2f} (-%{pct:.0f})\n\n"
                        f"Kuralların diyor ki: ya sat ({p.symbol} {p.qty:.4f} adet) ya da "
                        f"seviyeyi yeniden değerlendir."
                    )
                    await context.bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            logger.warning("Stop-loss kontrolu hatali (%s): %s", user_id, e)


_last_stop_notify: dict = {}


def fmt(value: float, currency: str) -> str:
    sym = {"TRY": "₺", "USD": "$"}.get(currency, currency)
    return f"{value:,.2f} {sym}"


async def daily_summary_job(context: ContextTypes.DEFAULT_TYPE):
    for user_id in config.ALLOWED_USER_IDS:
        try:
            pf = await to_thread(portfolio.get_portfolio, user_id)
            watch = get_watchlist(user_id)
            lines = [
                "📅 <b>Gün Sonu Özeti</b>",
                f"🕐 {datetime.now(TZ_ISTANBUL):%d.%m.%Y %H:%M} (TR)",
                "",
                "<b>💼 Portföy</b>",
            ]
            if pf["positions"]:
                for p in pf["positions"][:8]:
                    arrow = "🟢" if p.unrealized_pnl >= 0 else "🔴"
                    lines.append(
                        f"• {arrow} {p.symbol}: {fmt(p.market_value, p.currency)} "
                        f"({p.unrealized_pnl:+,.2f})"
                    )
                for cur, total in pf["total_by_currency"].items():
                    lines.append(f"• {cur} toplam: {fmt(total, cur)}")
            else:
                lines.append("• Portföy boş")

            if watch:
                symbols = [w["symbol"] for w in watch]
                results = await to_thread(signals.scan_symbols, symbols)
                strong = [r for r in results if abs(r["score"]) >= 3]
                lines.append("")
                lines.append("<b>🎯 Öne Çıkan Sinyaller</b>")
                if strong:
                    for r in strong[:5]:
                        lines.append(f"• {r['emoji']} {r['symbol']}: {r['signal']} (skor {r['score']:+d})")
                else:
                    lines.append("• Bugün belirgin al/sat sinyali yok")
                lines.append("")
                lines.append("<b>📊 Günün Hareketleri (takip listesi)</b>")
                movers = await _watch_summary(user_id, top=5)
                lines += movers if movers else ["• Veri yok"]
            lines.append("")
            lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
            await context.bot.send_message(chat_id=user_id, text="\n".join(lines))
        except Exception as e:
            logger.warning("Gun sonu ozeti gonderilemedi (%s): %s", user_id, e)


def setup_jobs(app) -> None:
    q = app.job_queue
    if q is None:
        return
    q.run_repeating(
        check_alerts_job, interval=config.ALERT_CHECK_SECONDS, first=15
    )
    q.run_repeating(
        signal_digest_job, interval=config.SCAN_MINUTES * 60, first=180
    )
    q.run_daily(
        daily_summary_job,
        time=dtime(hour=18, minute=30, tzinfo=TZ_ISTANBUL),
    )
    # Asistan gorevleri
    q.run_daily(
        morning_checkin_job,
        time=dtime(hour=9, minute=0, tzinfo=TZ_ISTANBUL),
        name="morning_checkin",
    )
    q.run_daily(
        evening_checkin_job,
        time=dtime(hour=20, minute=0, tzinfo=TZ_ISTANBUL),
        name="evening_checkin",
    )
    q.run_daily(
        salary_day_job,
        time=dtime(hour=9, minute=30, tzinfo=TZ_ISTANBUL),
        name="salary_day",
    )
    # BIST seans acilisi (hafta ici)
    q.run_daily(
        session_open_job,
        time=dtime(hour=10, minute=5, tzinfo=TZ_ISTANBUL),
        days=(0, 1, 2, 3, 4),
        name="bist_open",
    )
    # Yatirim hedefi hatirlatmasi (ayin 15'i ve 28'i)
    q.run_daily(
        invest_reminder_job,
        time=dtime(hour=12, minute=0, tzinfo=TZ_ISTANBUL),
        name="invest_reminder",
    )
    # Haftalik rapor (Pazar)
    q.run_daily(
        weekly_report_job,
        time=dtime(hour=19, minute=0, tzinfo=TZ_ISTANBUL),
        days=(6,),
        name="weekly_report",
    )
    # Otomatik hisse secimi (her gun 15:00)
    q.run_daily(
        auto_pick_job,
        time=dtime(hour=15, minute=0, tzinfo=TZ_ISTANBUL),
        name="auto_pick",
    )
    # Stop-loss kontrolu (6 saatte bir)
    q.run_repeating(
        stop_loss_job, interval=6 * 3600, first=300
    )
    logger.info(
        "Zamanlanmis gorevler kuruldu: alarm=%ss, sinyal=%sdk, ozet=18:30, "
        "asistan=09:00/20:00, maas=09:30, bist=10:05, yatirim=12:00, "
        "otomatik secim=15:00, stop-loss=6s, haftalik=Paz 19:00",
        config.ALERT_CHECK_SECONDS,
        config.SCAN_MINUTES,
    )
