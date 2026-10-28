"""Telegram komut isleyicileri.

Tum komutlar yalnizca ALLOWED_USER_IDS icindeki kullanicilara aciktir.
"""
import asyncio
import functools

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from database import (
    add_alert,
    add_cash,
    add_emergency_savings,
    add_watch,
    clear_pending_expense,
    delete_alert,
    get_alerts,
    get_cash,
    get_transactions,
    get_user_plan,
    get_watchlist,
    has_pending_expense,
    register_user,
    remove_watch,
    set_cash,
    set_pending_expense,
    set_user_plan,
)
from services import assistant, budget, charts, indicators as ind, market_data as md, nlp, portfolio, signals

CUR_SYM = {"TRY": "₺", "USD": "$"}


def restricted(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and user.id not in config.ALLOWED_USER_IDS:
            await update.message.reply_text(
                "⛔ Bu bot kişisel kullanım içindir.\n"
                f"Yetkiniz yok. user_id'niz: <code>{user.id}</code>\n"
                "Bu id'yi .env dosyasındaki ALLOWED_USER_IDS'e ekleyin."
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


# ---------- Yardimcilar ----------

async def to_thread(fn, *args):
    return await asyncio.to_thread(fn, *args)


def fmt_money(value: float, currency: str = "TRY") -> str:
    symbol = CUR_SYM.get(currency, currency)
    return f"{value:,.2f} {symbol}"


def parse_number(text: str) -> float | None:
    """TR ve ABD formatinda sayi girisini kabul eder."""
    t = text.strip().replace(" ", "")
    if "," in t and "." in t:
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


DISCLAIMER = "\n⚠️ <i>Bu teknik analizdir, yatırım tavsiyesi değildir.</i>"


def symbol_text(sym: str, resolved: tuple) -> str:
    s, kind, cur = resolved
    k = {"bist": "🇹🇷 BIST", "us": "🇺🇸 ABD", "crypto": "🪙 Kripto",
         "fx": "💱 Döviz", "commodity": "🥇 Emtia"}.get(kind, kind)
    return f"{s} ({k})"


# ---------- Komutlar ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username or "", user.first_name or "")
    text = (
        f"👋 Merhaba <b>{user.first_name}</b>! Kişisel finans ve yatırım botuna hoş geldin.\n\n"
        "🤖 <b>Kişisel finans asistanına</b> hoş geldin!\n\n"
        "📌 <b>Ben neler yapıyorum?</b>\n"
        "• 🧭 2 dakikada sana özel plan kuruyorum (/basla)\n"
        "• 💰 Maaşını otomatik bölüyorum (gider / harcama / birikim)\n"
        "• 🌅 Her sabah hatırlatıyorum, 🌙 akşam soru soruyorum\n"
        "• 🎉 Maaş gününde dağılımı söylüyorum\n"
        "• 📊 BIST + ABD + Kripto takip ve sade dil analiz\n\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        "Botu aktifleştirmek için bu ID'yi .env dosyasındaki "
        "ALLOWED_USER_IDS'e ekleyin ve botu yeniden başlatın.\n\n"
        "📖 Komut listesi için: /yardim"
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Komut Rehberi</b>\n\n"
        "<b>📊 Piyasa</b>\n"
        "/hisse SYMBOL — anlık fiyat + analiz (örn: THYAO, AAPL, BTC)\n"
        "/analiz SYMBOL — detaylı teknik analiz\n"
        "/dolar — güncel döviz kurları\n\n"
        "<b>🔔 Takip & Sinyal</b>\n"
        "/takip SYMBOL — takip listesine ekle\n"
        "/takipler — takip listen\n"
        "/silah SYMBOL — listeden çıkar\n"
        "/sinyal — tüm listeni tara, sinyalleri göster\n"
        "/alarm SYMBOL FIYAT [ust|alt] — fiyat alarmı\n"
        "/alarmlar — alarmların\n"
        "/alarmsil ID — alarmı sil\n\n"
        "<b>💼 Portföy</b>\n"
        "/ekle SYMBOL ADET FIYAT — alım kaydet\n"
        "/sat SYMBOL ADET FIYAT — satış kaydet\n"
        "/portfoy — portföy özeti ve kar/zarar\n"
        "/islemler — işlem geçmişi\n\n"
        "<b>💰 Maaş & Bütçe</b>\n"
        "/maas TUTAR — aylık maaşını tanımla\n"
        "/yatirim TUTAR — aylık yatırım hedefi\n"
        "/harcama TUTAR KATEGORİ — gider ekle\n"
        "/butce — bütçe durumu\n"
        "/rapor — aylık rapor\n\n"
        "⚠️ <i>Sinyaller yatırım tavsiyesi değildir.</i>"
    )
    await update.message.reply_text(text)


async def send_quote(update: Update, arg: str) -> bool:
    """Sembol sorgusunu yanitlar (hem /hisse hem dogal dil kullanir)."""
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı. Örnek: THYAO, AAPL, BTC, XU100")
        return False
    sym, kind, cur = resolved
    quote = await to_thread(md.get_quote, sym)
    name = await to_thread(md.get_name, sym)
    if not quote:
        await update.message.reply_text("❌ Fiyat verisi alınamadı, biraz sonra tekrar deneyin.")
        return False

    df = await to_thread(md.get_history, sym)
    analysis = await to_thread(ind.full_analysis, df) if df is not None and not df.empty else None

    open_status = "🟢 Açık" if md.is_market_open(sym) else "🔴 Kapalı"
    lines = [
        f"📊 <b>{sym}</b> — {name}",
        f"💱 Para: {cur} | 🕐 Piyasa: {open_status} ({md.market_hours_text(sym)})",
        "",
        f"💰 <b>Fiyat: {fmt_money(quote['price'], cur)}</b>",
    ]
    if quote["change"] >= 0:
        lines.append(f"📈 Günlük: <b>+{quote['change']:,.2f}</b> (+{quote['change_pct']:.2f}%)")
    else:
        lines.append(f"📉 Günlük: <b>{quote['change']:,.2f}</b> ({quote['change_pct']:.2f}%)")
    lines.append(f"📅 Gün içi: {fmt_money(quote['low'], cur)} – {fmt_money(quote['high'], cur)}")

    if analysis:
        lines += [
            "",
            "📈 <b>Teknik Özet</b>",
            f"• RSI(14): {analysis['rsi']:.1f} → {ind.rsi_label(analysis['rsi'])}",
            f"• MACD: {'pozitif' if analysis['macd_hist'] >= 0 else 'negatif'} ({'güçleniyor' if analysis['macd_hist'] > analysis['macd_hist_prev'] else 'zayıflıyor'})",
            f"• Trend: {ind.trend_label(analysis['price'], analysis['sma20'], analysis['sma50'])}",
            f"• Destek: {fmt_money(analysis['support'], cur)} | Direnç: {fmt_money(analysis['resistance'], cur)}",
        ]
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))
    return True


@restricted
async def cmd_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/hisse THYAO</code> veya <code>/hisse AAPL</code> veya <code>/hisse BTC</code>")
        return
    await send_quote(update, arg)


@restricted
async def cmd_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/analiz THYAO</code>")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    df = await to_thread(md.get_history, sym)
    if df is None or df.empty:
        await update.message.reply_text("❌ Veri alınamadı.")
        return
    a = await to_thread(ind.full_analysis, df)
    name = await to_thread(md.get_name, sym)

    # Gorsel: once grafik, sonra metin
    try:
        img = await to_thread(charts.build_chart, sym)
        if img:
            await update.message.reply_photo(
                photo=InputFile(img, filename=f"{sym}.png"),
                caption=f"🖼️ <b>{sym}</b> grafiği (fiyat + SMA + Bollinger + RSI)",
            )
    except Exception:
        pass  # grafik basarisiz olursa sadece metin gider

    vr = a.get("vol_ratio")
    vol_line = f"{vr:.1f}x (ortalama)" if vr else "—"
    lines = [
        f"🔬 <b>Detaylı Analiz: {sym}</b> — {name}",
        "",
        f"💵 Fiyat: {fmt_money(a['price'], cur)}",
        f"📉 RSI(14): <b>{a['rsi']:.1f}</b> ({ind.rsi_label(a['rsi'])})",
        f"📊 MACD: {a['macd']:.2f} | Sinyal: {a['macd_signal']:.2f} | Hist: {a['macd_hist']:.2f}",
        f"📐 SMA20: {fmt_money(a['sma20'], cur)} | SMA50: {fmt_money(a['sma50'], cur)}",
        f"📏 Bollinger: {fmt_money(a['bb_lower'], cur)} – {fmt_money(a['bb_upper'], cur)}",
        f"🧱 Destek: {fmt_money(a['support'], cur)} | Direnç: {fmt_money(a['resistance'], cur)}",
        f"🌊 ATR(14): {fmt_money(a['atr'], cur)} (volatilite)",
        f"📦 Hacim: {vol_line}",
        f"🕐 Piyasa: {md.market_hours_text(sym)}",
        "",
        f"🖼️ Büyük görsel için: <code>/grafik {sym}</code>",
    ]
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    period = _arg(context, 1) or "3mo"
    if not arg:
        await update.message.reply_text(
            "Kullanım: <code>/grafik SYMBOL [PERIYOT]</code>\n"
            "Periyot: 1mo, 3mo, 6mo, 1y (varsayılan: 3mo)\n"
            "Örn: <code>/grafik THYAO 6mo</code>"
        )
        return
    if period not in ("1mo", "3mo", "6mo", "1y"):
        await update.message.reply_text("❌ Geçersiz periyot. 1mo, 3mo, 6mo, 1y kullan.")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    img = await to_thread(charts.build_chart, sym, period)
    if not img:
        await update.message.reply_text("❌ Grafik için yeterli veri yok (en az 25 gün).")
        return
    await update.message.reply_photo(
        photo=InputFile(img, filename=f"{sym}.png"),
        caption=f"🖼️ <b>{sym}</b> — son {period}",
    )


@restricted
async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    watch = get_watchlist(user.id)
    if not watch:
        await update.message.reply_text(
            "📭 Takip listen boş.\n"
            "Önce <code>/takip THYAO</code> gibi komutlarla hisse ekle, "
            "sonra <code>/sinyal</code> ile tarat."
        )
        return
    symbols = [w["symbol"] for w in watch]
    await update.message.reply_text(f"🔍 {len(symbols)} varlık taranıyor, biraz bekleyin...")
    results = await to_thread(signals.scan_symbols, symbols)
    if not results:
        await update.message.reply_text("⚠️ Tarama sonucu alınamadı. Veri kaynağında sorun olabilir.")
        return

    lines = ["🎯 <b>Takip Listesi Sinyalleri</b>\n"]
    for r in results:
        direction = f"({r['change_pct']:+.2f}%)" if "change_pct" in r else ""
        stop_emoji = "🛑" if r["score"] >= 1 else "🎯"
        lines.append(
            f"{r['emoji']} <b>{r['symbol']}</b> — {r['signal']} (skor {r['score']:+d})\n"
            f"   💰 {fmt_money(r['price'], r['currency'])} {direction}\n"
            f"   📉 RSI {r['rsi']:.0f} | {r['trend']}\n"
            f"   {stop_emoji} Stop: {fmt_money(r['stop'], r['currency'])} | Hedef: {fmt_money(r['target'], r['currency'])}"
        )
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_watch_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/takip THYAO</code>")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    add_watch(update.effective_user.id, sym)
    await update.message.reply_text(f"✅ <b>{sym}</b> takip listesine eklendi. ({symbol_text(sym, resolved)})")


@restricted
async def cmd_watch_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    watch = get_watchlist(user.id)
    if not watch:
        await update.message.reply_text("📭 Takip listen boş. <code>/takip SYMBOL</code> ile ekle.")
        return
    symbols = [w["symbol"] for w in watch]
    quotes = await to_thread(md.get_quotes_batch, symbols)
    lines = ["👀 <b>Takip Listen</b>\n"]
    for w in watch:
        sym = w["symbol"]
        q = quotes.get(sym)
        if q:
            ch = f"<b>+{q['change_pct']:.2f}%</b>" if q["change_pct"] >= 0 else f"<b>{q['change_pct']:.2f}%</b>"
            lines.append(f"• <b>{sym}</b>: {fmt_money(q['price'], q['currency'])} ({ch})")
        else:
            lines.append(f"• <b>{sym}</b>: veri yok")
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_watch_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/silah THYAO</code>")
        return
    sym = arg.strip().upper()
    if remove_watch(update.effective_user.id, sym):
        await update.message.reply_text(f"🗑️ <b>{sym}</b> takip listesinden çıkarıldı.")
    else:
        await update.message.reply_text(f"❌ <b>{sym}</b> takip listenizde yok.")


@restricted
async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pf = await to_thread(portfolio.get_portfolio, user.id)
    if not pf["positions"]:
        await update.message.reply_text(
            "💼 Portföyün boş.\n"
            "Alım kaydı için: <code>/ekle THYAO 100 250</code>"
        )
        return

    lines = ["💼 <b>Portföy Özeti</b>\n"]
    for p in pf["positions"]:
        if p.unrealized_pnl >= 0:
            pnl = f"<b>+{p.unrealized_pnl:,.2f}</b> (+{p.unrealized_pct:.1f}%) 🟢"
        else:
            pnl = f"<b>{p.unrealized_pnl:,.2f}</b> ({p.unrealized_pct:.1f}%) 🔴"
        realized = ""
        if abs(p.realized_pnl) > 0.005:
            realized = f" | Gerçekleşen: {p.realized_pnl:+,.2f}"
        lines.append(
            f"• <b>{p.symbol}</b> — {p.qty:,.4f} adet\n"
            f"  Maliyet: {fmt_money(p.avg_cost, p.currency)} | Anlık: {fmt_money(p.current_price, p.currency)}\n"
            f"  Değer: <b>{fmt_money(p.market_value, p.currency)}</b> | K/Z: {pnl}{realized}"
        )

    lines.append("")
    for cur, total in pf["total_by_currency"].items():
        lines.append(f"📊 {cur} toplam: <b>{fmt_money(total, cur)}</b>")

    grand, base = await to_thread(_grand_total, pf["total_by_currency"])
    lines.append(f"\n💰 Genel toplam: <b>{fmt_money(grand, base)}</b>")
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


def _grand_total(total_by_currency: dict):
    base = config.BASE_CURRENCY
    if base in total_by_currency and len(total_by_currency) == 1:
        return total_by_currency[base], base
    grand = 0.0
    for cur, val in total_by_currency.items():
        if cur == base:
            grand += val
            continue
        rate = 1.0
        if cur == "USD" and base == "TRY":
            rate = md.get_fx_rate("TRY=X") or 1.0
        elif cur == "TRY" and base == "USD":
            r = md.get_fx_rate("TRY=X")
            rate = (1 / r) if r else 1.0
        grand += val * rate
    return grand, base


@restricted
async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, side: str):
    parts = context.args
    if len(parts) < 3:
        verb = "ekle" if side == "BUY" else "sat"
        await update.message.reply_text(
            f"Kullanım: <code>/{verb} SYMBOL ADET FIYAT</code>\n"
            f"Örnek: <code>/{verb} THYAO 100 250</code>"
        )
        return
    qty = parse_number(parts[1])
    price = parse_number(parts[2])
    note = " ".join(parts[3:]) if len(parts) > 3 else ""
    if qty is None or qty <= 0 or price is None or price <= 0:
        await update.message.reply_text("❌ Adet ve fiyat pozitif sayı olmalı.")
        return
    resolved = await to_thread(md.resolve_symbol, parts[0])
    if not resolved:
        await update.message.reply_text(f"❌ <b>{parts[0]}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    verb = "ALIŞ" if side == "BUY" else "SATIŞ"
    if side == "BUY":
        await to_thread(portfolio.buy, update.effective_user.id, sym, qty, price, cur, note)
        cash_delta = -(qty * price)
    else:
        await to_thread(portfolio.sell, update.effective_user.id, sym, qty, price, cur, note)
        cash_delta = qty * price
    new_balance = await to_thread(add_cash, update.effective_user.id, cash_delta)
    await update.message.reply_text(
        f"✅ <b>{verb} kaydedildi</b>\n"
        f"📌 {sym}: {qty:,.4f} adet × {fmt_money(price, cur)} = {fmt_money(qty * price, cur)}\n"
        f"💰 Nakit: {new_balance:,.2f} ₺"
    )


@restricted
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_trade(update, context, "BUY")


@restricted
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_trade(update, context, "SELL")


@restricted
async def cmd_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sym_arg = _arg(context, 0)
    sym = sym_arg.strip().upper() if sym_arg else None
    txns = await to_thread(get_transactions, user.id, sym)
    if not txns:
        await update.message.reply_text("📭 İşlem kaydı yok.")
        return
    lines = ["🧾 <b>İşlem Geçmişi</b> (son 20)\n"]
    for t in txns[-20:]:
        emoji = "🟢" if t["side"] == "BUY" else "🔴"
        lines.append(
            f"{emoji} {t['created_at'][:16]} | <b>{t['symbol']}</b> "
            f"{'AL' if t['side'] == 'BUY' else 'SAT'} {t['qty']:,.4f} @ {fmt_money(t['price'], t['currency'])}"
        )
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_number(_arg(context, 0) or "")
    if val is None or val <= 0:
        await update.message.reply_text("Kullanım: <code>/maas 50000</code>")
        return
    b = _get_budget_row(update.effective_user.id)
    invest = b["invest_amount"] if b and b["invest_amount"] else 0.0
    await to_thread(budget.set_plan, update.effective_user.id, val, invest)
    await update.message.reply_text(f"✅ Aylık maaş: <b>{fmt_money(val, 'TRY')}</b>\nYatırım hedefi: {fmt_money(invest, 'TRY')} (değiştirmek için /yatirim)")


@restricted
async def cmd_invest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = parse_number(_arg(context, 0) or "")
    if val is None or val <= 0:
        await update.message.reply_text("Kullanım: <code>/yatirim 10000</code>")
        return
    b = _get_budget_row(update.effective_user.id)
    salary = b["salary"] if b and b["salary"] else 0.0
    await to_thread(budget.set_plan, update.effective_user.id, salary, val)
    await update.message.reply_text(f"✅ Aylık yatırım hedefi: <b>{fmt_money(val, 'TRY')}</b>")


@restricted
async def cmd_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = context.args
    if len(parts) < 2:
        await update.message.reply_text(
            "Kullanım: <code>/harcama TUTAR KATEGORİ [NOT]</code>\n"
            "Örnek: <code>/harcama 1500 market</code>"
        )
        return
    amount = parse_number(parts[0])
    category = parts[1].strip().lower()
    note = " ".join(parts[2:]) if len(parts) > 2 else ""
    if amount is None or amount <= 0:
        await update.message.reply_text("❌ Tutar pozitif olmalı.")
        return
    await to_thread(budget.record_expense, update.effective_user.id, amount, category, note)
    new_balance = await to_thread(add_cash, update.effective_user.id, -amount)
    await update.message.reply_text(
        f"✅ Harcama kaydedildi: <b>{fmt_money(amount, 'TRY')}</b> — {category}\n"
        f"💰 Kalan nakit: {new_balance:,.2f} ₺"
    )


@restricted
async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    b = _get_budget_row(user.id)
    if not b or not b["salary"]:
        await update.message.reply_text(
            "📋 Bütçe planı tanımlı değil.\n"
            "/maas TUTAR → maaşını belirle\n"
            "/yatirim TUTAR → yatırım hedefini belirle"
        )
        return
    rep = await to_thread(budget.get_month_report, user.id)
    lines = [
        "📋 <b>Bütçe Durumu</b>",
        f"📅 Ay: {rep['month']}",
        f"💵 Maaş: {fmt_money(rep['salary'], 'TRY')}",
        f"🎯 Yatırım hedefi: {fmt_money(rep['invest_target'], 'TRY')} "
        f"({rep['invest_pct']:.0f}% tamamlandı)",
        f"📈 Bu ay yatırılan: <b>{fmt_money(rep['invested'], 'TRY')}</b>",
        f"🧾 Toplam harcama: {fmt_money(rep['total_expense'], 'TRY')} ({rep['n_expenses']} adet)",
        "",
        f"💰 Kalan: <b>{fmt_money(rep['remaining'], 'TRY')}</b>",
        f"💾 Tasarruf oranı: <b>%{rep['savings_rate']:.1f}</b>",
    ]
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rep = await to_thread(budget.get_month_report, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)

    lines = [
        "📑 <b>Aylık Rapor</b>",
        f"📅 {rep['month']}",
        "",
        "<b>💰 Bütçe</b>",
        f"• Maaş: {fmt_money(rep['salary'], 'TRY')}",
        f"• Harcamalar: {fmt_money(rep['total_expense'], 'TRY')}",
    ]
    if rep["by_category"]:
        for c in rep["by_category"][:5]:
            lines.append(f"   └ {c['category']}: {fmt_money(c['total'], 'TRY')} ({c['cnt']}x)")
    lines += [
        f"• Yatırılan: {fmt_money(rep['invested'], 'TRY')} / hedef {fmt_money(rep['invest_target'], 'TRY')} ({rep['invest_pct']:.0f}%)",
        f"• Kalan: <b>{fmt_money(rep['remaining'], 'TRY')}</b> | Tasarruf: %{rep['savings_rate']:.1f}",
        "",
        "<b>💼 Portföy</b>",
    ]
    if pf["positions"]:
        for p in pf["positions"][:10]:
            lines.append(
                f"• {p.symbol}: {fmt_money(p.market_value, p.currency)} "
                f"({p.unrealized_pnl:+,.2f})"
            )
        for cur, total in pf["total_by_currency"].items():
            lines.append(f"• {cur} toplam: {fmt_money(total, cur)}")
    else:
        lines.append("• Portföy boş")
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = context.args
    if len(parts) < 2:
        await update.message.reply_text(
            "Kullanım: <code>/alarm SYMBOL FIYAT [ust|alt]</code>\n"
            "• <code>ust</code> → fiyat hedefin üstüne çıkınca (varsayılan)\n"
            "• <code>alt</code> → fiyat hedefin altına inince\n"
            "Örnek: <code>/alarm THYAO 300 ust</code>"
        )
        return
    target = parse_number(parts[1])
    if target is None or target <= 0:
        await update.message.reply_text("❌ Hedef fiyat pozitif olmalı.")
        return
    direction = "above"
    if len(parts) > 2:
        d = parts[2].strip().lower()
        if d in ("alt", "below", "altı"):
            direction = "below"
    resolved = await to_thread(md.resolve_symbol, parts[0])
    if not resolved:
        await update.message.reply_text(f"❌ <b>{parts[0]}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    aid = add_alert(update.effective_user.id, sym, target, direction)
    d_text = "üstüne çıktığında" if direction == "above" else "altına indiğinde"
    await update.message.reply_text(
        f"🔔 Alarm kuruldu (ID: {aid})\n"
        f"📌 {sym} {fmt_money(target, cur)} seviyesinin {d_text} haber verilecek."
    )


@restricted
async def cmd_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    alerts = get_alerts(user.id, active_only=True)
    if not alerts:
        await update.message.reply_text("🔕 Aktif alarm yok. <code>/alarm SYMBOL FIYAT</code> ile kur.")
        return
    lines = ["🔔 <b>Aktif Alarmlar</b>\n"]
    for a in alerts:
        d = "↑ üst" if a["direction"] == "above" else "↓ alt"
        lines.append(f"• <b>ID {a['id']}</b> — {a['symbol']} {fmt_money(a['target_price'])} {d}")
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_alert_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    if not arg or not arg.isdigit():
        await update.message.reply_text("Kullanım: <code>/alarmsil ID</code> (ID için /alarmlar)")
        return
    if delete_alert(int(arg), update.effective_user.id):
        await update.message.reply_text(f"🗑️ Alarm <b>#{arg}</b> silindi.")
    else:
        await update.message.reply_text(f"❌ Alarm <b>#{arg}</b> bulunamadı.")


@restricted
async def cmd_fx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs = {"USD/TRY": "TRY=X", "EUR/TRY": "EURTRY=X", "EUR/USD": "EURUSD=X", "Altın (ons)": "GC=F"}
    lines = ["💱 <b>Güncel Kurlar</b>\n"]
    for label, sym in pairs.items():
        df = await to_thread(md.get_history, sym, "5d")
        if df is not None and not df.empty:
            price = float(df["Close"].iloc[-1])
            cur = "₺" if "TRY" in label else ("$" if "USD" in label or "Altın" in label else "")
            lines.append(f"• <b>{label}</b>: {price:,.2f} {cur}".rstrip())
        else:
            lines.append(f"• <b>{label}</b>: veri alınamadı")
    await update.message.reply_text("\n".join(lines))


# ---------- Asistan ----------

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


@restricted
async def cmd_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup(
        [
            [_btn("📊 Durumum", "menu:status")],
            [_btn("💰 Eldeki nakit", "menu:cash")],
            [_btn("🎯 Ne alayım / satayım", "menu:rebalance")],
            [_btn("📌 Bugün ne yapmalıyım?", "menu:today")],
            [_btn("📋 Planım", "menu:plan")],
            [_btn("💡 Bana öğret", "menu:tip")],
        ]
    )
    await update.message.reply_text(
        "🤖 <b>Asistan Menüsü</b>\n\nSana nasıl yardımcı olayım?", reply_markup=kb
    )


@restricted
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    lines = ["📊 <b>Durumun</b>\n"]
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        lines.append(assistant.emergency_status(plan, plan_row["emergency_saved"] or 0))
        cash = await to_thread(get_cash, user.id)
        rep = budget.get_month_report(user.id)
        lines.append(f"💰 Eldeki nakit: <b>{cash:,.2f} ₺</b>")
        lines.append(f"🧾 Bu ay kalan bütçe: <b>{rep['remaining']:,.2f} ₺</b>")
        lines.append(f"📈 Yatırım: {rep['invested']:,.2f} / {rep['invest_target']:,.2f} ₺ "
                     f"(%{rep['invest_pct']:.0f})")
        lines.append(f"📋 Harcama: {rep['total_expense']:,.2f} ₺ ({rep['n_expenses']} kayıt)")
    else:
        lines.append("📋 Planın yok. /basla ile 2 dakikada oluştur.")
        return await update.message.reply_text("\n".join(lines))

    pf = portfolio.get_portfolio(user.id)
    if pf["positions"]:
        lines.append("")
        lines.append("<b>💼 Portföy</b>")
        for p in pf["positions"][:5]:
            arrow = "🟢" if p.unrealized_pnl >= 0 else "🔴"
            lines.append(f"• {arrow} {p.symbol}: {p.market_value:,.2f} ({p.unrealized_pnl:+,.2f})")
    else:
        lines.append("\n💼 Portföyün boş. Alım yapınca /ekle ile kaydet.")
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


@restricted
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    action = q.data.split(":")[1]
    plan_row = get_user_plan(user.id)
    plan = assistant.plan_from_json(plan_row["plan"]) if plan_row else None
    saved = plan_row["emergency_saved"] or 0 if plan_row else 0

    if action == "status":
        await cmd_status(update, context)
    elif action == "cash":
        await cmd_cash(update, None)
    elif action == "rebalance":
        await cmd_rebalance(update, None)
    elif action == "today":
        rep = budget.get_month_report(user.id)
        text = assistant.today_action(plan, saved, rep["invested"], rep["invest_target"])
        await q.message.reply_text(text + DISCLAIMER)
    elif action == "plan":
        if plan:
            await q.message.reply_text(assistant.describe_plan(plan, saved))
        else:
            await q.message.reply_text("📋 Planın yok. /basla ile oluştur.")
    elif action == "tip":
        await q.message.reply_text(f"💡 <b>Bilgi Notu</b>\n\n{assistant.tip_of_day()}")


@restricted
async def checkin_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    if q.data == "checkin:expense:yes":
        set_pending_expense(user.id)
        await q.edit_message_text(
            "💸 Tamam! Harcamanı şu formatta yaz:\n"
            "<code>TUTAR KATEGORİ</code>\n"
            "Örn: <code>250 market</code>\n\n"
            "Örnek kategoriler: market, fatura, ulaşım, eğlence, kira, sağlık..."
        )
    else:
        rep = budget.get_month_report(user.id)
        await q.edit_message_text(
            f"✅ Harika, bugün harcama yapmadın! 🎉\n"
            f"Bu ay toplam: {rep['total_expense']:,.2f} ₺ | "
            f"Kalan: <b>{rep['remaining']:,.2f} ₺</b>"
        )


@restricted
async def salary_received_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await q.edit_message_text("📋 Planın yok. /basla ile oluştur.")
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    add_emergency_savings(user.id, plan["emergency_share"])
    new_saved = (plan_row["emergency_saved"] or 0) + plan["emergency_share"]
    new_cash = await to_thread(add_cash, user.id, plan["salary"])
    lines = [
        "🎉 <b>Yeni ay başladı, planın hazır!</b>\n",
        f"💰 Maaşın eklendi, eldeki nakit: <b>{new_cash:,.2f} ₺</b>",
        f"🏠 Zorunlu giderler: {plan['needs']:,.2f} ₺",
        f"🎉 İsteğe bağlı: {plan['wants']:,.2f} ₺",
        f"💾 Birikim: {plan['savings']:,.2f} ₺ "
        f"(acil fon: {plan['emergency_share']:,.2f} ₺ + yatırım: {plan['invest_share']:,.2f} ₺)",
        "",
        assistant.emergency_status(plan, new_saved),
    ]
    if plan["invest_share"] > 0:
        lines += [
            "",
            "📈 Yatırım payını değerlendirmek için: /sinyal",
        ]
    lines.append(DISCLAIMER)
    await q.edit_message_text("\n".join(lines))


@restricted
async def respond_nlp(update: Update, parsed: dict) -> bool:
    """Dogal dil niyetini yanitlar. Taninirsa True doner."""
    action = parsed["action"]
    symbol = parsed.get("symbol")
    if action == "price" and symbol:
        return await send_quote(update, symbol)
    if action == "signal" and symbol:
        await send_quote(update, symbol)
        sig = await to_thread(signals.score_symbol, symbol)
        if sig:
            await update.message.reply_text(
                "🧠 <b>Sade Yorum:</b> " + assistant.simple_signal_hint(sig) + DISCLAIMER
            )
        return True
    if action == "expense":
        await cmd_budget(update, None)
        return True
    if action == "cash":
        await cmd_cash(update, None)
        return True
    if action == "rebalance":
        await cmd_rebalance(update, None)
        return True
    if action == "portfolio":
        await cmd_portfolio(update, None)
        return True
    if action == "signals":
        await cmd_signal(update, None)
        return True
    if action == "status":
        await cmd_status(update, None)
        return True
    if action == "tip":
        await update.message.reply_text(f"💡 <b>Bilgi Notu</b>\n\n{assistant.tip_of_day()}")
        return True
    if action == "plan":
        plan_row = get_user_plan(update.effective_user.id)
        if plan_row:
            plan = assistant.plan_from_json(plan_row["plan"])
            await update.message.reply_text(assistant.describe_plan(plan, plan_row["emergency_saved"] or 0))
        else:
            await update.message.reply_text("📋 Planın yok. 2 dakikada oluşturalım: <code>/basla</code>")
        return True
    return False


@restricted
async def cmd_cash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/nakit [TUTAR] — eldeki nakdi gosterir veya ayarlar."""
    user = update.effective_user
    arg = _arg(context, 0)
    if arg:
        val = parse_number(arg)
        if val is None or val < 0:
            await update.message.reply_text("❌ Geçersiz tutar. Örn: <code>/nakit 20000</code>")
            return
        balance = await to_thread(set_cash, user.id, val)
        await update.message.reply_text(
            f"💰 Nakit bakiyen <b>{balance:,.2f} ₺</b> olarak ayarlandı.\n"
            "Bundan sonra maaş/harcama/alım/satışlar otomatik güncellenir."
        )
        return

    cash = await to_thread(get_cash, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)
    invested = sum(p.market_value for p in pf["positions"])
    total = cash + invested
    lines = [
        "💰 <b>Eldeki Para Durumu</b>",
        f"💵 Nakit: <b>{cash:,.2f} ₺</b>",
        f"📈 Yatırımlar: {invested:,.2f} ₺ ({len(pf['positions'])} pozisyon)",
        f"🏦 Toplam servet: <b>{total:,.2f} ₺</b>",
    ]
    if total <= 0:
        lines.append("", "İlk bakiyeni gir: <code>/nakit 20000</code>")
    lines.append("", "Dağılımı dengelemek için: /dengele")
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_salary_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/maasgunu GUN — maas gununu degistirir (onboarding'i bozmadan)."""
    user = update.effective_user
    arg = _arg(context, 0)
    if not arg or not arg.isdigit() or not (1 <= int(arg) <= 31):
        await update.message.reply_text(
            "Kullanım: <code>/maasgunu 8</code>\n"
            "Maaşını ayın kaçında alıyorsan o sayıyı yaz (1-31)."
        )
        return
    day = int(arg)
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await update.message.reply_text("📋 Önce plan kur: <code>/basla</code>")
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    plan["salary_day"] = day
    set_user_plan(user.id, plan["salary"], plan["expenses"], plan["risk"], plan["goal"],
                  day, plan["emergency_target"], assistant.plan_to_json(plan))
    await update.message.reply_text(
        f"📆 Maaş günün <b>ayın {day}. günü</b> olarak güncellendi.\n"
        "Her ay o gün sana dağılımı hatırlatacağım. 🎉"
    )


@restricted
async def cmd_rebalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/dengele — plan hedefine gore al/sat onerileri."""
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await update.message.reply_text("📋 Önce plan kur: <code>/basla</code>")
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    pf = await to_thread(portfolio.get_portfolio, user.id)
    cash = await to_thread(get_cash, user.id)
    msg = assistant.rebalance_message(plan, pf["positions"], cash)
    await update.message.reply_text(msg)


@restricted
async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Serbest metin: harcama kaydi, dogal dil komutu veya yardim menusu."""
    user = update.effective_user
    if has_pending_expense(user.id):
        parts = update.message.text.strip().split(None, 1)
        amount = parse_number(parts[0]) if parts else None
        category = parts[1].strip().lower() if len(parts) > 1 else "genel"
        if amount is None or amount <= 0:
            await update.message.reply_text(
                "❌ Format: <code>TUTAR KATEGORİ</code>\nÖrn: <code>250 market</code>"
            )
            return
        budget.record_expense(user.id, amount, category)
        clear_pending_expense(user.id)
        new_balance = await to_thread(add_cash, user.id, -amount)
        rep = budget.get_month_report(user.id)
        await update.message.reply_text(
            f"✅ <b>{amount:,.2f} ₺</b> ({category}) kaydedildi!\n"
            f"💰 Kalan nakit: <b>{new_balance:,.2f} ₺</b>\n"
            f"🧾 Bu ay kalan bütçe: <b>{rep['remaining']:,.2f} ₺</b>\n\n"
            "İyi iş! Her harcamayı kaydetmek bütçeni korur. 💪"
        )
        return

    # Dogal dil komutlari
    parsed = nlp.parse(update.message.text)
    if parsed["action"] and await respond_nlp(update, parsed):
        return

    await update.message.reply_text(
        "👋 Merhaba! Sana nasıl yardımcı olabilirim?\n\n"
        "Sadece yazman yeterli, örneğin:\n"
        "• \"BTC ne durumda?\" → fiyat + analiz\n"
        "• \"THYAO alınır mı?\" → sade yorum\n"
        "• \"Bu ay ne kadar harcadım?\" → bütçe\n"
        "• \"Portföyüm nasıl?\" → durum\n\n"
        "Komut listesi: /yardim | Asistan menüsü: /asistan"
    )


# ---------- Kayit ----------

def _arg(context: ContextTypes.DEFAULT_TYPE, idx: int) -> str:
    return context.args[idx] if context.args and idx < len(context.args) else ""


def _get_budget_row(user_id: int):
    from database import get_budget
    return get_budget(user_id)


def register_handlers(app) -> None:
    # Onboarding sohbet akisi, catch-all metin isleyiciden ONCE eklenmeli
    from bot.onboarding import onboarding_handler
    app.add_handler(onboarding_handler())

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("yardim", cmd_help))
    app.add_handler(CommandHandler("hisse", cmd_quote))
    app.add_handler(CommandHandler("analiz", cmd_analysis))
    app.add_handler(CommandHandler("grafik", cmd_chart))
    app.add_handler(CommandHandler("sinyal", cmd_signal))
    app.add_handler(CommandHandler("takip", cmd_watch_add))
    app.add_handler(CommandHandler("takipler", cmd_watch_list))
    app.add_handler(CommandHandler("silah", cmd_watch_remove))
    app.add_handler(CommandHandler("portfoy", cmd_portfolio))
    app.add_handler(CommandHandler("ekle", cmd_buy))
    app.add_handler(CommandHandler("sat", cmd_sell))
    app.add_handler(CommandHandler("islemler", cmd_transactions))
    app.add_handler(CommandHandler("maas", cmd_salary))
    app.add_handler(CommandHandler("yatirim", cmd_invest))
    app.add_handler(CommandHandler("harcama", cmd_expense))
    app.add_handler(CommandHandler("butce", cmd_budget))
    app.add_handler(CommandHandler("rapor", cmd_report))
    app.add_handler(CommandHandler("alarm", cmd_alert))
    app.add_handler(CommandHandler("alarmlar", cmd_alerts))
    app.add_handler(CommandHandler("alarmsil", cmd_alert_remove))
    app.add_handler(CommandHandler("dolar", cmd_fx))
    app.add_handler(CommandHandler("asistan", cmd_assistant))
    app.add_handler(CommandHandler("durum", cmd_status))
    app.add_handler(CommandHandler("nakit", cmd_cash))
    app.add_handler(CommandHandler("maasgunu", cmd_salary_day))
    app.add_handler(CommandHandler("dengele", cmd_rebalance))

    # Buton geri cagirmalari
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(checkin_expense_callback, pattern=r"^checkin:expense:"))
    app.add_handler(CallbackQueryHandler(salary_received_callback, pattern=r"^salary:"))

    # Serbest metin (bekleyen harcama kaydi / yardim) EN SONA eklenmeli
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
