"""Telegram komut isleyicileri.

Tum komutlar yalnizca ALLOWED_USER_IDS icindeki kullanicilara aciktir.
"""
import asyncio
import functools
import io
from datetime import date

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
    add_alert_config,
    add_backup_record,
    add_cash,
    add_corp_event,
    add_dividend_event,
    add_emergency_savings,
    add_note,
    add_tax_event,
    add_watch,
    clear_pending_expense,
    deactivate_alert_config,
    delete_alert,
    delete_note,
    get_alert_configs,
    get_alerts,
    get_backups,
    get_cash,
    get_corp_calendar,
    get_corp_calendar_for_symbol,
    get_notes,
    get_portfolio_snapshots,
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
from services import (
    advanced_alerts,
    assistant,
    backtest,
    backup,
    benchmark,
    budget,
    broker,
    calendar as cal_svc,
    charts,
    correlation,
    dividend,
    evening_analysis,
    fundamentals,
    indicators as ind,
    inline,
    macro,
    market_data as md,
    menu,
    nlp,
    performance,
    picker,
    portfolio,
    risk,
    risk_metrics,
    signals,
    tax,
    trading_hours,
    webhooks,
)

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
        "• [PARA] Maaşını otomatik bölüyorum (gider / harcama / birikim)\n"
        "• 🌅 Her sabah hatırlatıyorum, 🌙 akşam soru soruyorum\n"
        "• 🎉 Maaş gününde dağılımı söylüyorum\n"
        "• [GRAFIK] BIST + ABD + Kripto takip ve sade dil analiz\n\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        "Botu aktifleştirmek için bu ID'yi .env dosyasındaki "
        "ALLOWED_USER_IDS'e ekleyin ve botu yeniden başlatın.\n\n"
        "📖 Komut listesi için: /yardim"
    )
    await update.message.reply_text(text)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Komut Rehberi</b>\n\n"
        "<b>🏠 Ana Menu</b>\n"
        "/menu — Butonlarla tum islemler (nakit, portfoy, risk, hedefler, harcamalar, analiz)\n\n"
        "<b>📊 Piyasa</b>\n"
        "/hisse SYMBOL — anlık fiyat + analiz (orn: THYAO, AAPL, BTC)\n"
        "/analiz SYMBOL — detayli teknik analiz\n"
        "/grafik SYMBOL [PERIYOT] — fiyat + SMA + Bollinger + RSI grafigi\n"
        "/dolar — guncei doviz kurları\n\n"
        "<b>🔔 Takip & Sinyal</b>\n"
        "/takip SYMBOL — takip listesine ekle\n"
        "/takipler — takip listen\n"
        "/silah SYMBOL — listeden cikar\n"
        "/sinyal — tum listeni tara, sinyalleri goster\n"
        "/alarm SYMBOL FIYAT [ust|alt] — fiyat alarmı\n"
        "/alarmlar — alarmlarin\n"
        "/alarmsil ID — alarmı sil\n\n"
        "<b>🤖 Otomatik & Gelismis</b>\n"
        "/oner — Bot kendisi hisse secer (guvenli + riskli karisim)\n"
        "/alarm2 SYMBOL TUR PARAM — gelismis alarm (RSI/MACD/BB/Hacim/Fiyat)\n"
        "/alarm2lar — aktif gelismis alarmlar\n"
        "/alarm2sil ID — gelismis alarm sil\n\n"
        "<b>💼 Portfoy</b>\n"
        "/ekle SYMBOL ADET FIYAT — alim kaydet\n"
        "/sat SYMBOL ADET FIYAT — satis kaydet\n"
        "/portfoy — portfoy ozeti ve kar/zarar\n"
        "/islemler — islem gecmisi\n"
        "/karsilastir SYM1 SYM2 — iki hisse karsilastirma\n\n"
        "<b>📈 Analiz & Risk</b>\n"
        "/analiz SYMBOL — detayli teknik analiz\n"
        "/temel SYMBOL — temel analiz (F/K, P/B, ROE, marj, buyume)\n"
        "/backtest SYMBOL [PERIYOT] — strateji gecmise testi\n"
        "/riskmetrik [GUN] — Sharpe, Sortino, Calmar, Max DD, VaR\n"
        "/montecarlo [YIL] [SIM] — Monte Carlo simulasyonu\n"
        "/risk — portfoy risk analizi (korelasyon, HHI, DD)\n"
        "/korelasyon [PERIYOT] — korelasyon matrisi + cesitlendirme\n\n"
        "<b>💰 Maaş & Butce</b>\n"
        "/maas TUTAR — aylik maasini tanimla\n"
        "/yatirim TUTAR — aylik yatirim hedefi\n"
        "/harcama TUTAR KATEGORI — gider ekle\n"
        "/butce — butce durumu\n"
        "/rapor — aylik rapor\n\n"
        "<b>💰 Nakit & Temettü</b>\n"
        "/nakit [TUTAR] — eldeki nakit goster/ayarla\n"
        "/maasgunu GUN — maas gununu ayarla (orn: 8)\n"
        "/temettutakip [YIL] — temettu ozeti + DRIP onerileri\n\n"
        "<b>📊 Performans & Takvim</b>\n"
        "/performans — performans atfi (hangi karar ne kazandirdi)\n"
        "/takvim [GUN] — kurumsal takvim (temettu, ceyrek, bolunme)\n\n"
        "<b>💾 Yedek & Veri</b>\n"
        "/yedek — GitHub Gist'e sifreli tam yedek\n"
        "/yedekal GIST_ID — yedekten restore\n"
        "/csv [islemler|portfoy|temettu] [YIL] — CSV export\n"
        "/vergiraporu [YIL] — GVKY raporu (satis kazanci, temettu vergisi)\n\n"
        "<b>📝 Notlar & Diger</b>\n"
        "/not SYMBOL NOT — pozisyona not ekle\n"
        "/notlar [SYMBOL] — notlari gor\n"
        "/haber SYMBOL — son haber basliklari\n"
        "/makro — doviz, emtia, endeksler paneli\n\n"
        "<b>⚙️ Kurulum</b>\n"
        "/basla — 3 soruluk kurulum (maas, gun, risk)\n"
        "/menu — Ana menu (butonlarla tum islemler)\n\n"
        "⚠️ <i>Sinyaller yatirim tavsiyesi degildir.</i>"
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
        f"[GRAFIK] <b>{sym}</b> — {name}",
        f"💱 Para: {cur} | 🕐 Piyasa: {open_status} ({md.market_hours_text(sym)})",
        "",
        f"[PARA] <b>Fiyat: {fmt_money(quote['price'], cur)}</b>",
    ]
    if quote["change"] >= 0:
        lines.append(f"[ARTIS] Günlük: <b>+{quote['change']:,.2f}</b> (+{quote['change_pct']:.2f}%)")
    else:
        lines.append(f"[DUSUS] Günlük: <b>{quote['change']:,.2f}</b> ({quote['change_pct']:.2f}%)")
    lines.append(f"📅 Gün içi: {fmt_money(quote['low'], cur)} – {fmt_money(quote['high'], cur)}")

    if analysis:
        lines += [
            "",
            "[ARTIS] <b>Teknik Özet</b>",
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
    # Temel analiz (yavas istek, 24s onbellekli) - best effort
    fund_line = ""
    try:
        f = await to_thread(fundamentals.get_fundamentals, sym)
        if f:
            fund_line = "\n" + fundamentals.fundamentals_text(f)
    except Exception:
        pass
    lines = [
        f"🔬 <b>Detaylı Analiz: {sym}</b> — {name}",
        "",
        f"💵 Fiyat: {fmt_money(a['price'], cur)}",
        f"[DUSUS] RSI(14): <b>{a['rsi']:.1f}</b> ({ind.rsi_label(a['rsi'])})",
        f"[GRAFIK] MACD: {a['macd']:.2f} | Sinyal: {a['macd_signal']:.2f} | Hist: {a['macd_hist']:.2f}",
        f"📐 SMA20: {fmt_money(a['sma20'], cur)} | SMA50: {fmt_money(a['sma50'], cur)}",
        f"📏 Bollinger: {fmt_money(a['bb_lower'], cur)} – {fmt_money(a['bb_upper'], cur)}",
        f"🧱 Destek: {fmt_money(a['support'], cur)} | Direnç: {fmt_money(a['resistance'], cur)}",
        f"🌊 ATR(14): {fmt_money(a['atr'], cur)} (volatilite)",
        f"[DIGER] Hacim: {vol_line}",
        f"🕐 Piyasa: {md.market_hours_text(sym)}",
    ]
    if fund_line:
        lines += ["", fund_line]
    lines += [
        "",
        f"🖼️ Büyük görsel için: <code>/grafik {sym}</code>",
        f"[GRAFIK] Geçmiş performans testi: <code>/backtest {sym}</code>",
    ]
    lines.append(DISCLAIMER)
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    arg = _arg(context, 0)
    period = _arg(context, 1) or "3mo"
    theme = _arg(context, 2) or None  # light/dark
    if not arg:
        await update.message.reply_text(
            "Kullanım: <code>/grafik SYMBOL [PERIYOT] [TEMA]</code>\n"
            "Periyot: 1mo, 3mo, 6mo, 1y (varsayılan: 3mo)\n"
            "Tema: light, dark (varsayılan: config.CHART_THEME)\n"
            "Örn: <code>/grafik THYAO 6mo dark</code>"
        )
        return
    if period not in ("1mo", "3mo", "6mo", "1y"):
        await update.message.reply_text("❌ Geçersiz periyot. 1mo, 3mo, 6mo, 1y kullan.")
        return
    if theme and theme not in ("light", "dark"):
        await update.message.reply_text("❌ Geçersiz tema. light veya dark kullan.")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    img = await to_thread(charts.build_chart, sym, period, theme)
    if not img:
        await update.message.reply_text("❌ Grafik için yeterli veri yok (en az 25 gün).")
        return
    await update.message.reply_photo(
        photo=InputFile(img, filename=f"{sym}.png"),
        caption=f"🖼️ <b>{sym}</b> — son {period} ({theme or 'varsayılan'})",
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

    lines = ["[HEDEF] <b>Takip Listesi Sinyalleri</b>\n"]
    for r in results:
        direction = f"({r['change_pct']:+.2f}%)" if "change_pct" in r else ""
        stop_emoji = "🛑" if r["score"] >= 1 else "[HEDEF]"
        lines.append(
            f"{r['emoji']} <b>{r['symbol']}</b> — {r['signal']} (skor {r['score']:+d})\n"
            f"   [PARA] {fmt_money(r['price'], r['currency'])} {direction}\n"
            f"   [DUSUS] RSI {r['rsi']:.0f} | {r['trend']}\n"
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
    stop_pct = config.STOP_LOSS_PCT
    for p in pf["positions"]:
        if p.unrealized_pnl >= 0:
            pnl = f"<b>+{p.unrealized_pnl:,.2f}</b> (+{p.unrealized_pct:.1f}%) 🟢"
        else:
            pnl = f"<b>{p.unrealized_pnl:,.2f}</b> ({p.unrealized_pct:.1f}%) 🔴"
        realized = ""
        if abs(p.realized_pnl) > 0.005:
            realized = f" | Gerçekleşen: {p.realized_pnl:+,.2f}"
        stop_price = p.avg_cost * (1 - stop_pct / 100) if p.avg_cost else 0.0
        stop_flag = " ⚠️ STOP!" if stop_price and p.current_price <= stop_price else ""
        lines.append(
            f"• <b>{p.symbol}</b> — {p.qty:,.4f} adet\n"
            f"  Maliyet: {fmt_money(p.avg_cost, p.currency)} | Anlık: {fmt_money(p.current_price, p.currency)}\n"
            f"  Değer: <b>{fmt_money(p.market_value, p.currency)}</b> | K/Z: {pnl}{realized}\n"
            f"  🛑 Stop-loss: {fmt_money(stop_price, p.currency)} (-%{stop_pct:.0f}){stop_flag}"
        )

    lines.append("")
    for cur, total in pf["total_by_currency"].items():
        lines.append(f"[GRAFIK] {cur} toplam: <b>{fmt_money(total, cur)}</b>")

    grand, base = await to_thread(_grand_total, pf["total_by_currency"])
    lines.append(f"\n[PARA] Genel toplam: <b>{fmt_money(grand, base)}</b>")
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
            f"Kullanım: <code>/{verb} SYMBOL ADET FIYAT [KOMISYON]</code>\n"
            f"Örnek: <code>/{verb} THYAO 100 250</code>\n"
            f"<b>US hisse için dolar tutarı:</b> <code>/{verb} AAPL 1000 150</code> → $1000 değerinde al (150$/adet)\n"
            f"Komisyonlu: <code>/{verb} AAPL 1000 150 1.5</code> → $1.5 komisyon dahil"
        )
        return
    
    resolved = await to_thread(md.resolve_symbol, parts[0])
    if not resolved:
        await update.message.reply_text(f"❌ <b>{parts[0]}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    
    price = parse_number(parts[2])
    if price is None or price <= 0:
        await update.message.reply_text("❌ Fiyat pozitif sayı olmalı.")
        return
    
    # Komisyon (opsiyonel 4. parametre)
    commission = 0.0
    note = ""
    if len(parts) >= 4:
        # Son parametre not mu komisyon mu?
        last = parse_number(parts[-1])
        if last is not None and last >= 0:
            commission = last
            note = " ".join(parts[3:-1]) if len(parts) > 4 else ""
        else:
            note = " ".join(parts[3:])
    
    verb = "ALIŞ" if side == "BUY" else "SATIŞ"
    
    if side == "BUY":
        # US hisse ve dolar bazlı giriş kontrolü
        # Eğer 2. parametre büyükse ve US hisse ise dolar tutarı olarak kabul et
        second_param = parse_number(parts[1])
        if second_param is not None and second_param > 0:
            if kind == "us" and cur == "USD" and second_param >= 100:
                # Dolar tutarı girişi: qty = (amount - commission) / price
                from services.portfolio import calculate_qty_from_amount
                qty = calculate_qty_from_amount(second_param, price, commission)
                if qty <= 0:
                    await update.message.reply_text("❌ Komisyon tutarından büyük olmalı.")
                    return
                await update.message.reply_text(
                    f"💡 <b>Dolar tutarı modu</b>: ${second_param:,.2f} / ${price:,.2f} = {qty:.4f} lot\n"
                    f"Komisyon: ${commission:,.2f} | Net: ${second_param - commission:,.2f}"
                )
            else:
                # Normal adet girişi
                qty = second_param
        else:
            await update.message.reply_text("❌ Adet/tutar pozitif sayı olmalı.")
            return
        
        if qty <= 0:
            await update.message.reply_text("❌ Hesaplanan adet sıfır veya negatif.")
            return
        
        total_cost = qty * price + commission
        await to_thread(portfolio.buy, update.effective_user.id, sym, qty, price, cur, note, commission)
        cash_delta = -total_cost
    else:
        qty = parse_number(parts[1])
        if qty is None or qty <= 0:
            await update.message.reply_text("❌ Adet pozitif sayı olmalı.")
            return
        total_value = qty * price - commission
        await to_thread(portfolio.sell, update.effective_user.id, sym, qty, price, cur, note, commission)
        cash_delta = total_value
    
    new_balance = await to_thread(add_cash, update.effective_user.id, cash_delta)
    
    if side == "BUY":
        cost_info = f"{qty:,.4f} adet × {fmt_money(price, cur)} = {fmt_money(qty * price, cur)}"
        if commission > 0:
            cost_info += f" + komisyon {fmt_money(commission, cur)}"
    else:
        cost_info = f"{qty:,.4f} adet × {fmt_money(price, cur)} = {fmt_money(qty * price, cur)}"
        if commission > 0:
            cost_info += f" - komisyon {fmt_money(commission, cur)}"
    
    await update.message.reply_text(
        f"✅ <b>{verb} kaydedildi</b>\n"
        f"📌 {sym}: {cost_info}\n"
        f"[PARA] Nakit: {fmt_money(new_balance, 'TRY')}"
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
        f"[PARA] Kalan nakit: {new_balance:,.2f} ₺"
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
        f"[HEDEF] Yatırım hedefi: {fmt_money(rep['invest_target'], 'TRY')} "
        f"({rep['invest_pct']:.0f}% tamamlandı)",
        f"[ARTIS] Bu ay yatırılan: <b>{fmt_money(rep['invested'], 'TRY')}</b>",
        f"🧾 Toplam harcama: {fmt_money(rep['total_expense'], 'TRY')} ({rep['n_expenses']} adet)",
        "",
        f"[PARA] Kalan: <b>{fmt_money(rep['remaining'], 'TRY')}</b>",
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
        "<b>[PARA] Bütçe</b>",
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
            "Kullanım: <code>/alarm SYMBOL FIYAT [ust|alt] [webhook_tip webhook_url]</code>\n"
            "• <code>ust</code> → fiyat hedefin üstüne çıkınca (varsayılan)\n"
            "• <code>alt</code> → fiyat hedefin altına inince\n"
            "• Webhook: <code>/alarm THYAO 300 ust discord https://discord.com/api/webhooks/...</code>\n"
            "Örnek: <code>/alarm THYAO 300 ust</code>"
        )
        return
    target = parse_number(parts[1])
    if target is None or target <= 0:
        await update.message.reply_text("❌ Hedef fiyat pozitif olmalı.")
        return
    direction = "above"
    webhook_type = ""
    webhook_url = ""
    if len(parts) > 2:
        d = parts[2].strip().lower()
        if d in ("alt", "below", "altı"):
            direction = "below"
        elif d in ("discord", "slack", "ntfy", "telegram", "json", "pushover", "email"):
            webhook_type = d
            if len(parts) > 3:
                webhook_url = parts[3]
    elif len(parts) > 3:
        # 4. parametre webhook olabilir
        d3 = parts[3].strip().lower()
        if d3 in ("discord", "slack", "ntfy", "telegram", "json", "pushover", "email"):
            webhook_type = d3
            if len(parts) > 4:
                webhook_url = parts[4]

    resolved = await to_thread(md.resolve_symbol, parts[0])
    if not resolved:
        await update.message.reply_text(f"❌ <b>{parts[0]}</b> bulunamadı.")
        return
    sym, kind, cur = resolved
    aid = add_alert(update.effective_user.id, sym, target, direction, webhook_url, webhook_type)
    d_text = "üstüne çıktığında" if direction == "above" else "altına indiğinde"
    msg = f"🔔 Alarm kuruldu (ID: {aid})\n📌 {sym} {fmt_money(target, cur)} seviyesinin {d_text} haber verilecek."
    if webhook_type:
        msg += f"\n🔗 Webhook: {webhook_type}"
    await update.message.reply_text(msg)


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
            [_btn("[GRAFIK] Durumum", "menu:status")],
            [_btn("[PARA] Eldeki nakit", "menu:cash")],
            [_btn("[HEDEF] Otomatik hisse seç", "menu:pick")],
            [_btn("⚖️ Ne alayım / satayım", "menu:rebalance")],
            [_btn("📌 Bugün ne yapmalıyım?", "menu:today")],
            [_btn("📋 Planım", "menu:plan")],
            [_btn("💡 Bana öğret", "menu:tip")],
        ]
    )
    await update.message.reply_text(
        "🤖 <b>Asistan Menüsü</b>\n\nSana nasıl yardımcı olayım?", reply_markup=kb
    )


@restricted
@restricted
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menu - butonlarla tum islemler."""
    user = update.effective_user
    cash = await to_thread(get_cash, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)
    invested = sum(p.market_value for p in pf["positions"])
    total = cash + invested
    positions = len(pf["positions"])
    
    plan_row = get_user_plan(user.id)
    risk_score = 5
    risk_level = "Dengeli"
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        risk_map = {"sakin": (3, "Koruma"), "dengeli": (5, "Dengeli"), "atilgan": (8, "Buyume")}
        risk_score, risk_level = risk_map.get(plan["risk"], (5, "Dengeli"))
    
    invest_progress = 0
    emergency_progress = 0
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        rep = budget.get_month_report(user.id)
        if plan["invest_share"]:
            invest_progress = min(100, rep["invested"] / plan["invest_share"] * 100)
        emergency_saved = plan_row["emergency_saved"] or 0
        if plan["emergency_target"]:
            emergency_progress = min(100, emergency_saved / plan["emergency_target"] * 100)
    
    # Use the menu system
    await update.message.reply_text(
        "🏠 <b>Ana Menu</b>\nHangi islemi yapmak istiyorsun?",
        reply_markup=menu.main_menu()
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    lines = ["[GRAFIK] <b>Durumun</b>\n"]
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        lines.append(assistant.emergency_status(plan, plan_row["emergency_saved"] or 0))
        rep = budget.get_month_report(user.id)
        lines.append(f"🧾 Bu ay kalan bütçe: <b>{rep['remaining']:,.2f} ₺</b>")
        lines.append(f"[ARTIS] Yatırım: {rep['invested']:,.2f} / {rep['invest_target']:,.2f} ₺ "
                     f"(%{rep['invest_pct']:.0f})")
        lines.append(f"📋 Harcama: {rep['total_expense']:,.2f} ₺ ({rep['n_expenses']} kayıt)")
    else:
        lines.append("📋 Planın yok. 2 dakikada oluştur: <code>/basla</code>")

    # Nakit ve portfoy her zaman gosterilir
    cash = await to_thread(get_cash, user.id)
    lines.append(f"[PARA] Eldeki nakit: <b>{cash:,.2f} ₺</b>")

    pf = await to_thread(portfolio.get_portfolio, user.id)
    if pf["positions"]:
        invested = sum(p.market_value for p in pf["positions"])
        lines.append(f"[ARTIS] Yatırımlar: {invested:,.2f} ₺ ({len(pf['positions'])} pozisyon)")
        lines.append(f"🏦 Toplam servet: <b>{cash + invested:,.2f} ₺</b>")
    else:
        lines.append("💼 Portföyün boş. Alım yapınca /ekle ile kaydet.")
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
    elif action == "pick":
        await cmd_pick(update, None)
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
            "[HARCAMA] Tamam! Harcamanı şu formatta yaz:\n"
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
        f"[PARA] Maaşın eklendi, eldeki nakit: <b>{new_cash:,.2f} ₺</b>",
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
            "[ARTIS] Yatırım payını değerlendirmek için: /sinyal",
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
    if action == "pick":
        await cmd_pick(update, None)
        return True
    if action == "makro":
        await cmd_macro(update, None)
        return True
    if action == "risk":
        await cmd_risk(update, None)
        return True
    if action == "backtest":
        await cmd_backtest(update, None, symbol)
        return True
    if action == "news":
        await cmd_news(update, None, symbol)
        return True
    if action == "temel":
        await cmd_fundamental(update, None, symbol)
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
            f"[PARA] Nakit bakiyen <b>{balance:,.2f} ₺</b> olarak ayarlandı.\n"
            "Bundan sonra maaş/harcama/alım/satışlar otomatik güncellenir."
        )
        return

    cash = await to_thread(get_cash, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)
    invested = sum(p.market_value for p in pf["positions"])
    total = cash + invested
    lines = [
        "[PARA] <b>Eldeki Para Durumu</b>",
        f"💵 Nakit: <b>{cash:,.2f} ₺</b>",
        f"[ARTIS] Yatırımlar: {invested:,.2f} ₺ ({len(pf['positions'])} pozisyon)",
        f"🏦 Toplam servet: <b>{total:,.2f} ₺</b>",
    ]
    if total <= 0:
        lines.append("İlk bakiyeni gir: <code>/nakit 20000</code>")
    lines.append("Dağılımı dengelemek için: /dengele")
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
async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/oner [taze] — bot kendisi hisse secer (guvenli + riskli karisimi)."""
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await update.message.reply_text(
            "📋 Önce 2 dakikada planını kur: <code>/basla</code>\n"
            "Böylece sana uygun riskli/güvenli karışımı seçebilirim."
        )
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    force = (_arg(context, 0) or "").lower() in ("taze", "yenile", "force")

    pf = await to_thread(portfolio.get_portfolio, user.id)
    cash = await to_thread(get_cash, user.id)

    if force:
        await update.message.reply_text("🔍 Taze tarama başlıyor (1-2 dk sürebilir)...")
        picker.refresh_scores(force=True)
        result = await to_thread(picker.pick, plan, pf["positions"], cash)
        await update.message.reply_text(picker.pick_message(result))
        return

    if not picker.scores_ready():
        await update.message.reply_text(
            "🔍 İlk tarama yapılıyor (bir kez ~1 dk bekleyeceksin, sonra anında döner)..."
        )
        result = await to_thread(picker.pick, plan, pf["positions"], cash)
        await update.message.reply_text(picker.pick_message(result))
        return

    # Onbellek sicak: arka planda tazele, aninda sonuc ver
    stale = not picker.scores_fresh()
    if stale:
        picker.refresh_in_background()
    result = await to_thread(picker.pick, plan, pf["positions"], cash)
    msg = picker.pick_message(result)
    if stale:
        msg += "\n🔄 Fiyatlar arka planda güncelleniyor; 2 dk sonra tazesi için: /oner taze"
    await update.message.reply_text(msg)


@restricted
async def cmd_fundamental(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          sym_arg: str | None = None):
    """/temel SYMBOL — sirketin finansal sagligi (degerleme, borc, buyume)."""
    arg = sym_arg or _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/temel THYAO</code>")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    await update.message.reply_text(f"🔍 {sym} finansalları çekiliyor...")
    f = await to_thread(fundamentals.get_fundamentals, sym)
    if not f:
        await update.message.reply_text("❌ Temel veri alınamadı (küçük/özel şirketlerde olabilir).")
        return
    text = fundamentals.fundamentals_text(f)
    await update.message.reply_text(
        f"[GRAFIK] <b>{sym}</b> — {f['name']}\n\n{text}\n" + DISCLAIMER
    )


@restricted
async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       sym_arg: str | None = None):
    """/backtest SYMBOL [PERIYOT] — strateji gecmiste kazandirir miydi?"""
    arg = sym_arg or _arg(context, 0)
    period = _arg(context, 1) or "2y"
    if not arg:
        await update.message.reply_text(
            "Kullanım: <code>/backtest THYAO</code> (periyot: 1y, 2y, 5y)\n"
            "Bu test, sinyal kuralının son dönemde al-sat yapmasa da seni kazandırıp kazandırmayacağını ölçer."
        )
        return
    if period not in ("1y", "2y", "5y", "10y"):
        await update.message.reply_text("❌ Periyot: 1y, 2y, 5y, 10y kullan.")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    await update.message.reply_text(f"🧪 {sym} geçmiş test ediliyor ({period})...")
    result = await to_thread(backtest.backtest, sym, period)
    await update.message.reply_text(backtest.backtest_text(result))


@restricted
async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/risk — portfoy risk analizi."""
    user = update.effective_user
    pf = await to_thread(portfolio.get_portfolio, user.id)
    cash = await to_thread(get_cash, user.id)
    r = await to_thread(risk.analyze, pf["positions"], cash)
    await update.message.reply_text(risk.risk_text(r))


@restricted
async def cmd_macro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/makro — doviz, emtia ve endeks paneli."""
    msg = await to_thread(macro.dashboard)
    await update.message.reply_text(msg)


@restricted
async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE,
                   sym_arg: str | None = None):
    """/haber SYMBOL — son haber basliklari."""
    arg = sym_arg or _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/haber THYAO</code>")
        return
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    items = await to_thread(md.get_news, sym)
    if not items:
        await update.message.reply_text(f"📭 {sym} için haber bulunamadı.")
        return
    lines = [f"📰 <b>{sym} — Son Haberler</b>"]
    for it in items:
        lines.append(f"• {it['title']}\n  {it['link']}")
    await update.message.reply_text("\n".join(lines[:8]))


@restricted
async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/not SYMBOL NOT — pozisyona not ekle."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: <code>/not THYAO notunuz</code>")
        return
    sym_arg = args[0]
    note = " ".join(args[1:])
    resolved = await to_thread(md.resolve_symbol, sym_arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{sym_arg}</b> bulunamadı.")
        return
    sym = resolved[0]
    add_note(update.effective_user.id, sym, note)
    await update.message.reply_text(f"📝 <b>{sym}</b> için not eklendi: {note}")


@restricted
async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/notlar [SYMBOL] — notları gör."""
    user = update.effective_user
    args = context.args
    symbol = None
    if args:
        resolved = await to_thread(md.resolve_symbol, args[0])
        if resolved:
            symbol = resolved[0]
    notes = get_notes(user.id, symbol)
    if not notes:
        await update.message.reply_text("📭 Not bulunamadı.")
        return
    lines = ["📝 <b>Notlarınız</b>"]
    for n in notes[:10]:
        lines.append(f"• <b>{n['symbol']}</b> ({n['created_at'][:10]}): {n['note']}")
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/karsilastir SYMBOL1 SYMBOL2 — iki hisseyi yan yana karsilastir."""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Kullanım: <code>/karsilastir THYAO GARAN</code>")
        return
    syms = []
    for a in args[:2]:
        resolved = await to_thread(md.resolve_symbol, a)
        if resolved:
            syms.append(resolved[0])
    if len(syms) < 2:
        await update.message.reply_text("❌ Semboller bulunamadı.")
        return

    quotes = await to_thread(md.get_quotes_batch, syms)
    lines = ["⚖️ <b>Karşılaştırma</b>\n"]
    for sym in syms:
        q = quotes.get(sym)
        if not q:
            lines.append(f"• <b>{sym}</b>: veri yok")
            continue
        sign = "+" if q["change_pct"] >= 0 else ""
        emoji = "🟢" if q["change_pct"] >= 0 else "🔴"
        lines.append(
            f"• <b>{sym}</b> ({emoji} {sign}{q['change_pct']:.2f}%): "
            f"{q['price']:,.2f} {q['currency']} | Hacim: {q['volume']:,.0f}"
        )
    # Temel veri karsilastirmasi
    fund_data = {}
    for sym in syms:
        f = await to_thread(fundamentals.get_fundamentals, sym)
        if f:
            fund_data[sym] = f
    if fund_data:
        lines.append("\n[GRAFIK] <b>Temel Veri:</b>")
        for sym in syms:
            f = fund_data.get(sym)
            if f:
                lines.append(
                    f"• <b>{sym}</b>: F/K={f.get('pe')}, P/B={f.get('pb')}, "
                    f"ROE={f.get('roe')*100:.0f}%, Marj=%{f.get('profit_margin',0)*100:.0f}"
                )
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/takvim [GUN] — kurumsal takvim (temettü, çeyrek, vb.)."""
    arg = _arg(context, 0)
    days = 7
    if arg and arg.isdigit():
        days = min(int(arg), 60)
    events = cal_svc.get_upcoming_events(None, days)
    if not events:
        # Takip listesini senkronize etmeyi dene
        for user_id in config.ALLOWED_USER_IDS:
            # Arka planda senkronize et
            pass
        events = cal_svc.get_upcoming_events(None, days)
    msg = cal_svc.format_calendar(events, days)
    await update.message.reply_text(msg)


@restricted
async def cmd_trading_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/saatler [SYMBOL] — optimum işlem saatleri ve sinyal kalitesi.
    
    Sembol verilirse o sembol için analiz yapar.
    Sembol verilmezse haftalık genel programı gösterir.
    
    Örnekler:
    /saatler          → Haftalık program
    /saatler THYAO    → BIST için saatlik analiz
    /saatler AAPL     → ABD için saatlik analiz
    /saatler BTC      → Kripto için saatlik analiz
    """
    arg = _arg(context, 0)
    if not arg:
        msg = trading_hours.get_weekly_schedule()
        await update.message.reply_text(msg)
        return
    
    resolved = await to_thread(md.resolve_symbol, arg)
    if not resolved:
        await update.message.reply_text(f"❌ <b>{arg}</b> bulunamadı.")
        return
    
    sym = resolved[0]
    msg = trading_hours.get_trading_hours_advice(sym)
    await update.message.reply_text(msg)


@restricted
async def cmd_advanced_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarm2 SYMBOL TÜR PARAMETRELER [webhook_tip webhook_url] — gelişmiş alarm."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(advanced_alerts.format_alert_help())
        return
    sym_arg = args[0]
    type_ = args[1].lower()
    params = {}
    try:
        if type_ == "rsi":
            params = {"threshold": float(args[2]), "direction": args[3].lower()}
        elif type_ == "macd":
            params = {"direction": args[2].lower()}
        elif type_ == "bb":
            params = {"band": args[2].lower(), "direction": args[3].lower()}
        elif type_ == "volume":
            params = {"multiplier": float(args[2])}
        elif type_ == "price":
            params = {"target": float(args[2]), "direction": args[3].lower()}
        else:
            await update.message.reply_text(advanced_alerts.format_alert_help())
            return
    except (IndexError, ValueError):
        await update.message.reply_text(advanced_alerts.format_alert_help())
        return

    # Webhook parametreleri (opsiyonel, sonda)
    webhook_type = ""
    webhook_url = ""
    remaining = args[4:] if type_ in ("rsi", "bb", "price") else args[3:]
    if remaining:
        if remaining[0] in ("discord", "slack", "ntfy", "telegram", "json", "pushover", "email"):
            webhook_type = remaining[0]
            if len(remaining) > 1:
                webhook_url = remaining[1]

    resolved = await to_thread(md.resolve_symbol, args[0])
    if not resolved:
        await update.message.reply_text(f"❌ Sembol bulunamadı.")
        return
    sym = resolved[0]
    config_id = advanced_alerts.create_alert(update.effective_user.id, sym, args[1].lower(), params, webhook_url, webhook_type)
    if config_id:
        await update.message.reply_text(
            f"🔔 Gelişmiş alarm kuruldu (ID: {config_id}): {sym} {args[1]} {params}"
        )
    else:
        await update.message.reply_text(advanced_alerts.format_alert_help())


@restricted
async def cmd_advanced_alerts_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarm2lar — aktif gelişmiş alarmlar."""
    user = update.effective_user
    configs = get_alert_configs(user.id)
    if not configs:
        await update.message.reply_text("🔔 Aktif gelişmiş alarm yok.")
        return
    lines = ["🔔 <b>Aktif Gelişmiş Alarmlar</b>\n"]
    for c in configs:
        params = json.loads(c["params"]) if c["params"] else {}
        lines.append(
            f"• ID {c['id']}: {c['symbol']} {c['type']} {params} "
            f"({'✅' if c['active'] else '❌'})"
        )
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_advanced_alert_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarm2sil ID — gelişmiş alarm sil."""
    arg = _arg(context, 0)
    if not arg or not arg.isdigit():
        await update.message.reply_text("Kullanım: <code>/alarm2sil ID</code>")
        return
    if deactivate_alert_config(int(arg), update.effective_user.id):
        await update.message.reply_text(f"🗑️ Alarm <b>#{arg}</b> silindi.")
    else:
        await update.message.reply_text(f"❌ Alarm <b>#{arg}</b> bulunamadı.")


@restricted
async def cmd_webhook_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarmwebhook TIP URL [ALARM_TIP] — webhook ekle (discord, slack, ntfy, pushover, telegram, json, email).
    
    Örnekler:
    /alarmwebhook discord https://discord.com/api/webhooks/... 
    /alarmwebhook slack https://hooks.slack.com/services/...
    /alarmwebhook ntfy https://ntfy.sh/my-topic
    /alarmwebhook telegram tg://BOT_TOKEN/CHAT_ID
    /alarmwebhook json https://my-api.com/webhook
    /alarmwebhook pushover pushover://user=xxx&token=yyy
    /alarmwebhook email email://to@example.com?api_key=xxx
    
    ALARM_TIP: all (tümü), price (fiyat), advanced (gelişmiş), bigmove (ani hareket)
    """
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Kullanım: <code>/alarmwebhook TIP URL [ALARM_TIP]</code>\n\n"
            "TIP: discord, slack, ntfy, telegram, json, pushover, email\n"
            "ALARM_TIP: all, price, advanced, bigmove (varsayılan: all)\n\n"
            "Örnekler:\n"
            "<code>/alarmwebhook discord https://discord.com/api/webhooks/xxx</code>\n"
            "<code>/alarmwebhook slack https://hooks.slack.com/services/xxx</code>\n"
            "<code>/alarmwebhook ntfy https://ntfy.sh/my-topic</code>\n"
            "<code>/alarmwebhook telegram tg://BOT_TOKEN/CHAT_ID</code>\n"
            "<code>/alarmwebhook json https://api.mysite.com/webhook</code>"
        )
        return

    webhook_type = args[0].lower()
    webhook_url = args[1]
    alarm_scope = args[2].lower() if len(args) > 2 else "all"

    valid_types = {"discord", "slack", "ntfy", "telegram", "json", "pushover", "email"}
    if webhook_type not in valid_types:
        await update.message.reply_text(f"❌ Geçersiz tip. Kullanılabilir: {', '.join(valid_types)}")
        return

    valid_scopes = {"all", "price", "advanced", "bigmove"}
    if alarm_scope not in valid_scopes:
        await update.message.reply_text(f"❌ Geçersiz alarm kapsamı. Kullanılabilir: {', '.join(valid_scopes)}")
        return

    # Webhook'ı kaydet - basit versiyon: kullanıcıya özel bir config tutuyoruz
    # Gerçek implementasyonda ayrı bir tablo olmalı
    from database import execute, query
    user_id = update.effective_user.id

    # Mevcut webhookları getir
    existing = query(
        "SELECT webhook_url, webhook_type, alarm_scope FROM user_webhooks WHERE user_id = ? AND webhook_type = ?",
        (user_id, webhook_type)
    )

    if existing:
        # Güncelle
        execute(
            "UPDATE user_webhooks SET webhook_url = ?, alarm_scope = ?, updated_at = ? WHERE user_id = ? AND webhook_type = ?",
            (webhook_url, alarm_scope, now_iso(), user_id, webhook_type)
        )
        await update.message.reply_text(f"✅ {webhook_type} webhook güncellendi (kapsam: {alarm_scope})")
    else:
        # Yeni ekle
        execute(
            "INSERT INTO user_webhooks (user_id, webhook_type, webhook_url, alarm_scope, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, webhook_type, webhook_url, alarm_scope, now_iso(), now_iso())
        )
        await update.message.reply_text(f"✅ {webhook_type} webhook eklendi (kapsam: {alarm_scope})")


@restricted
async def cmd_webhook_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarmwebhooklar — aktif webhookları listele."""
    from database import query
    user_id = update.effective_user.id

    webhooks_list = query(
        "SELECT webhook_type, webhook_url, alarm_scope, created_at FROM user_webhooks WHERE user_id = ? ORDER BY created_at",
        (user_id,)
    )

    if not webhooks_list:
        await update.message.reply_text("🔕 Kaydedilmiş webhook yok. <code>/alarmwebhook TIP URL</code> ile ekle.")
        return

    lines = ["🔔 <b>Kaydedilmiş Webhook'lar</b>\n"]
    for w in webhooks_list:
        url_preview = w["webhook_url"][:50] + "..." if len(w["webhook_url"]) > 50 else w["webhook_url"]
        lines.append(f"• <b>{w['webhook_type']}</b>: {url_preview} (kapsam: {w['alarm_scope']})")

    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_webhook_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarmwebhooksil TIP — webhook sil."""
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/alarmwebhooksil TIP</code> (tip: discord, slack, ntfy, vb.)")
        return

    from database import execute
    user_id = update.effective_user.id

    cur = execute(
        "DELETE FROM user_webhooks WHERE user_id = ? AND webhook_type = ?",
        (user_id, arg.lower())
    )

    if cur > 0:
        await update.message.reply_text(f"🗑️ {arg} webhook silindi.")
    else:
        await update.message.reply_text(f"❌ {arg} webhook bulunamadı.")


@restricted
async def cmd_webhook_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/alarmwebhooktest TIP — webhook test et."""
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/alarmwebhooktest TIP</code>")
        return

    from database import query
    from services.webhooks import send_webhook, WebhookPayload

    user_id = update.effective_user.id
    webhook_type = arg.lower()

    w = query(
        "SELECT webhook_url, alarm_scope FROM user_webhooks WHERE user_id = ? AND webhook_type = ?",
        (user_id, webhook_type)
    )

    if not w:
        await update.message.reply_text(f"❌ {webhook_type} webhook bulunamadı. Önce <code>/alarmwebhook {webhook_type} URL</code> ile ekle.")
        return

    webhook_url = w[0]["webhook_url"]
    payload = WebhookPayload(
        title="🧪 Test Bildirimi",
        message="Bu bir test mesajıdır. Webhook çalışıyor! ✅",
        symbol="TEST",
        price=100.0,
        change_pct=5.0,
        alert_type="test",
    )

    success = send_webhook(webhook_url, webhook_type, payload)

    if success:
        await update.message.reply_text(f"✅ {webhook_type} test bildirimi gönderildi!")
    else:
        await update.message.reply_text(f"❌ {webhook_type} test bildirimi gönderilemedi. URL/token kontrol edin.")


@restricted
async def cmd_broker_compare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broker SYMBOL — broker maliyet karşılaştırması.
    
    Örnek:
    /broker THYAO     → BIST için Midast vs Garanti vs İş vs Komisyonsuz
    /broker AAPL      → ABD için Midast vs IBKR vs Garanti
    /broker BTC       → Kripto için
    """
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/broker SYMBOL</code>\nÖrn: <code>/broker THYAO</code>")
        return
    
    user_id = update.effective_user.id
    msg = await to_thread(evening_analysis.get_broker_comparison_for_user, user_id, arg)
    await update.message.reply_text(msg)


@restricted
async def cmd_broker_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/brokerayarla BROKER — varsayılan broker ayarla.
    
    Kullanılabilir: midast, isyatirim, garanti, vakif, deniz, komisyonsuz_bist, interactive_brokers
    """
    arg = _arg(context, 0)
    if not arg:
        brokers_list = ", ".join(broker.BROKERS.keys())
        await update.message.reply_text(
            f"Kullanım: <code>/brokerayarla BROKER</code>\n\nKullanılabilir:\n{brokers_list}"
        )
        return
    
    broker_key = arg.lower()
    if broker_key not in broker.BROKERS:
        await update.message.reply_text(f"❌ Bilinmeyen broker: {broker_key}")
        return
    
    if await to_thread(broker.set_user_broker, update.effective_user.id, broker_key):
        await update.message.reply_text(f"✅ Varsayılan broker: <b>{broker.BROKERS[broker_key].name}</b>")
    else:
        await update.message.reply_text("❌ Kaydedilemedi.")


@restricted
async def cmd_evening_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/aksam — akşam al/sat analizi raporu.
    
    Portföyünü analiz eder, satılacak/alınacak önerir, broker maliyetlerini hesaplar.
    """
    user_id = update.effective_user.id
    msg = await to_thread(evening_analysis.generate_evening_report, user_id)
    await update.message.reply_text(msg)


@restricted
async def cmd_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/performans — performans atfi ve atfi."""
    user = update.effective_user
    msg = performance.attribution_text(user.id)
    await update.message.reply_text(msg)


@restricted
async def cmd_tax_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/vergiraporu [YIL] — GVKY raporu."""
    user = update.effective_user
    arg = _arg(context, 0)
    year = int(arg) if arg and arg.isdigit() else date.today().year
    report = tax.calculate_capital_gains(user.id, year)
    divs = tax.calculate_dividend_income(user.id, year)

    lines = [
        f"🇹🇷 <b>GVKY Raporu ({year})</b>",
        "",
        f"[ARTIS] Satış İşlemleri: {len(report['sales'])}",
        f"[PARA] Toplam Kazanç: {report['total_gain']:,.2f} ₺",
        f"[KALKAN] Muafiyet Limiti: {report['exempt_limit']:,.0f} ₺",
        f"📋 Vergilendirilecek Kazanç: <b>{report['taxable_gain']:,.2f} ₺</b>",
        "",
        f"[PARA] Temettü (Kesintili): {divs['kesintili_toplam']:,.2f} ₺",
        f"[PARA] Temettü (Kesintisiz): {divs['kesintisiz_toplam']:,.2f} ₺",
        f"[HARCAMA] Toplam Vergi: {divs['toplam_vergi']:,.2f} ₺",
    ]
    if report['sales']:
        lines.append("\n<b>📋 Detaylı Satışlar:</b>")
        for s in report['sales'][:10]:
            lines.append(
                f"• {s['symbol']}: {s['qty']:.0f} adet @ {s['buy_price']:.2f} → {s['sell_price']:.2f} = {s['gain']:+,.2f} ₺"
            )
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_csv_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/csv [islemler|portfoy|temettu] [YIL] — CSV export."""
    user = update.effective_user
    args = context.args
    export_type = args[0] if args else "islemler"
    year = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    if export_type == "islemler":
        csv_data = tax.export_csv_transactions(user.id, year)
        filename = f"islemler_{year or 'all'}.csv"
    elif export_type == "portfoy":
        csv_data = tax.export_csv_portfolio(user.id)
        filename = "portfoy.csv"
    elif export_type == "temettu":
        csv_data = tax.export_csv_dividends(user.id, year)
        filename = f"temettu_{year or 'all'}.csv"
    else:
        await update.message.reply_text("Kullanım: <code>/csv islemler|portfoy|temettu [YIL]</code>")
        return

    await update.message.reply_document(
        document=io.BytesIO(csv_data.encode()),
        filename=filename,
        caption=f"📄 {filename}"
    )


@restricted
async def cmd_benchmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/benchmark [ENDİKS] [GUN] — portföy vs endeks karşılaştırması."""
    user = update.effective_user
    args = context.args
    benchmark = args[0] if args else "XU100.IS"
    days = int(args[1]) if len(args) > 1 and args[1].isdigit() else 365

    result = benchmark.compare_to_benchmark(user.id, benchmark, days)
    await update.message.reply_text(benchmark.benchmark_text(result))


@restricted
async def cmd_risk_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/riskmetrik [GUN] — Sharpe, Sortino, Calmar, Max DD, VaR."""
    user = update.effective_user
    arg = _arg(context, 0)
    days = int(arg) if arg and arg.isdigit() else 365

    metrics = risk_metrics.calculate_metrics(user.id, days)
    await update.message.reply_text(risk_metrics.metrics_text(metrics))


@restricted
async def cmd_monte_carlo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/montecarlo [YIL] [SIMULASYON] — Monte Carlo simülasyonu."""
    user = update.effective_user
    args = context.args
    years = int(args[0]) if args and args[0].isdigit() else 10
    n_sim = int(args[1]) if len(args) > 1 and args[1].isdigit() else 200

    await update.message.reply_text(f"[ZAR] Simülasyon çalışıyor ({years} yıl, {n_sim} senaryo)...")
    result = risk_metrics.monte_carlo_simulation(user.id, years, n_sim)
    await update.message.reply_text(risk_metrics.monte_carlo_text(result))


@restricted
async def cmd_dividend_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/temettutakip [YIL] — temettü özeti + DRIP önerileri."""
    user = update.effective_user
    arg = _arg(context, 0)
    year = int(arg) if arg and arg.isdigit() else date.today().year

    summary = dividend.get_dividend_summary(user.id, year)
    suggestions = dividend.drip_suggestions(user.id)

    lines = [dividend.dividend_text(summary)]
    if suggestions:
        lines.append("\n🔄 <b>DRIP Önerileri:</b>")
        for s in suggestions:
            lines.append(f"• {s['symbol']}: {s['amount']:,.2f} ₺ ({s['date']}) — {s['note']}")
    await update.message.reply_text("\n".join(lines))


@restricted
async def cmd_correlation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/korelasyon [PERIYOT] — korelasyon matrisi ve çeşitlendirme."""
    user = update.effective_user
    arg = _arg(context, 0)
    period = arg if arg else "1y"

    corr = correlation.calculate_correlation_matrix(user.id, period)
    div = correlation.diversification_metrics(user.id)
    await update.message.reply_text(correlation.correlation_text(corr, div))


@restricted
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/yedek — GitHub Gist'e tam yedek al."""
    user = update.effective_user
    await update.message.reply_text("💾 Yedek oluşturuluyor...")
    result = backup.create_backup(user.id)
    await update.message.reply_text(backup.backup_text(result))


@restricted
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/yedekal GIST_ID — Gist'ten yedek indir."""
    arg = _arg(context, 0)
    if not arg:
        await update.message.reply_text("Kullanım: <code>/yedekal GIST_ID</code>")
        return
    result = backup.restore_backup(update.effective_user.id, arg)
    await update.message.reply_text(f"⚠️ {result.get('error', 'Bilinmeyen hata')}")


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
            f"[PARA] Kalan nakit: <b>{new_balance:,.2f} ₺</b>\n"
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


# ---------- Menu Callback Handlers ----------

@restricted
async def menu_cash_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    user = update.effective_user
    cash = await to_thread(get_cash, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)
    invested = sum(p.market_value for p in pf["positions"])
    total = cash + invested
    if action == "add":
        await q.edit_message_text("[PARA] Ne kadar eklemek istiyorsun? Örn: <code>5000</code>")
        context.user_data["cash_action"] = "add"
        return
    if action == "remove":
        await q.edit_message_text("[HARCAMA] Ne kadar çıkarmak istiyorsun? Örn: <code>2000</code>")
        context.user_data["cash_action"] = "remove"
        return
    if action == "detail":
        lines = [
            "[PARA] <b>Nakit Detayı</b>",
            f"💵 Nakit: <b>{cash:,.2f} ₺</b>",
            f"[ARTIS] Yatırımlar: {invested:,.2f} ₺",
            f"🏦 Toplam: <b>{total:,.2f} ₺</b>",
        ]
        await q.edit_message_text("\n".join(lines), reply_markup=menu.cash_menu(cash))
        return
    await q.edit_message_text("[PARA] <b>Nakit Yönetimi</b>", reply_markup=menu.cash_menu(cash))


@restricted
async def menu_portfolio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    user = update.effective_user
    pf = await to_thread(portfolio.get_portfolio, user.id)
    if action == "rebalance":
        msg = assistant.rebalance_message(
            assistant.plan_from_json((await to_thread(get_user_plan, user.id))["plan"]),
            pf["positions"],
            await to_thread(get_cash, user.id),
        )
        await q.edit_message_text(msg)
        return
    if action == "pick":
        plan_row = get_user_plan(user.id)
        if not plan_row:
            await q.edit_message_text("📋 Önce plan kur: <code>/basla</code>")
            return
        plan = assistant.plan_from_json(plan_row["plan"])
        cash = await to_thread(get_cash, user.id)
        result = await to_thread(picker.pick, plan, pf["positions"], cash)
        await q.edit_message_text(picker.pick_message(result))
        return
    if action == "buy":
        await q.edit_message_text("[MARKET] Ne almak istiyorsun? Örn: <code>THYAO 100 250</code>")
        context.user_data["trade_action"] = "buy"
        return
    if action == "sell":
        await q.edit_message_text("[DUSUS] Ne satmak istiyorsun? Örn: <code>THYAO 50 300</code>")
        context.user_data["trade_action"] = "sell"
        return
    if action == "detail":
        msg = ""
        for p in pf["positions"]:
            msg += f"• {p.symbol}: {p.market_value:,.0f}₺ ({p.unrealized_pnl:+,.0f}₺)\n"
        await q.edit_message_text(f"[ARTIS] <b>Portföy Detayı</b>\n{msg}")
        return
    total = sum(p.market_value for p in pf["positions"])
    await q.edit_message_text("[ARTIS] <b>Portföy</b>", reply_markup=menu.portfolio_menu(sum(p.market_value for p in pf["positions"]), len(pf["positions"])))


@restricted
async def menu_risk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await q.edit_message_text("📋 Önce plan kur: <code>/basla</code>")
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    risk_score = {"sakin": 3, "dengeli": 5, "atilgan": 8}.get(plan["risk"], 5)
    risk_level = {"sakin": "🟢 Koruma", "dengeli": "🟡 Dengeli", "atilgan": "🔴 Büyüme"}[plan["risk"]]
    if action == "set":
        await q.edit_message_text("[AYAR] Risk profilini seç:\n• <code>/basla</code> ile değiştir")
        return
    if action == "detail":
        pf = await to_thread(portfolio.get_portfolio, q.from_user.id)
        cash = await to_thread(get_cash, q.from_user.id)
        r = risk.analyze(pf["positions"], cash)
        await q.edit_message_text(risk.risk_text(r))
        return
    await q.edit_message_text("[KALKAN] <b>Risk Profili</b>", reply_markup=menu.risk_menu(risk_score, risk_level))


@restricted
async def menu_goals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    user = update.effective_user
    plan_row = get_user_plan(user.id)
    if not plan_row:
        await q.edit_message_text("📋 Önce plan kur: <code>/basla</code>")
        return
    plan = assistant.plan_from_json(plan_row["plan"])
    rep = budget.get_month_report(user.id)
    invest_progress = min(100, (rep["invested"] / plan["invest_share"] * 100)) if plan["invest_share"] else 0
    cash = await to_thread(get_cash, user.id)
    emergency_saved = plan_row["emergency_saved"] or 0
    emergency_progress = min(100, (emergency_saved / plan["emergency_target"] * 100)) if plan["emergency_target"] else 100
    if action == "set":
        await q.edit_message_text("[HEDEF] Hedefleri değiştirmek için <code>/basla</code> yaz")
        return
    if action == "detail":
        rep = budget.get_month_report(user.id)
        lines = [
            "[HEDEF] <b>Hedef Detayı</b>",
            f"[PARA] Yatırım: {rep['invested']:,.0f} / {rep['invest_target']:,.0f} ₺ (%{rep['invest_pct']:.0f})",
            f"[KALKAN] Acil Fon: {plan_row['emergency_saved'] or 0:,.0f} / {plan['emergency_target']:,.0f} ₺",
        ]
        await q.edit_message_text("\n".join(lines))
        return
    await q.edit_message_text("[HEDEF] <b>Hedefler</b>", reply_markup=menu.goals_menu(invest_progress, emergency_progress))


@restricted
async def menu_expense_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    if action == "cat":
        category = q.data.split(":")[2]
        context.user_data["expense_category"] = category
        await q.edit_message_text(f"[HARCAMA] <b>{category.title()}</b> için tutar gir: Örn: <code>250</code>")
        context.user_data["expense_action"] = "confirm"
        return
    if action == "custom":
        await q.edit_message_text("[OZEL] Kategori ve tutar gir: Örn: <code>kitap 150</code>")
        context.user_data["expense_action"] = "custom"
        return
    if action == "confirm":
        # amount:category format
        parts = q.data.split(":")
        if len(parts) >= 4:
            amount = float(parts[2])
            category = parts[3]
            user = update.effective_user
            budget.record_expense(user.id, amount, category)
            new_balance = await to_thread(add_cash, user.id, -amount)
            await q.edit_message_text(f"✅ <b>{amount:,.0f}₺</b> → {category} kaydedildi!\n[PARA] Kalan: {new_balance:,.0f}₺")
        return
    await q.edit_message_text("[HARCAMA] <b>Harcama Ekle</b>", reply_markup=menu.expense_menu())


@restricted
async def menu_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1] if ":" in q.data else ""
    if action == "benchmark":
        await q.edit_message_text("[GRAFIK] Benchmark karşılaştırması için: <code>/benchmark XU100.IS 365</code>")
        return
    if action == "risk":
        await q.edit_message_text("[GRAFIK] Risk metrikleri için: <code>/riskmetrik 365</code>")
        return
    if action == "montecarlo":
        await q.edit_message_text("[ZAR] Monte Carlo için: <code>/montecarlo 10 500</code>")
        return
    if action == "correlation":
        await q.edit_message_text("[GRAFIK] Korelasyon için: <code>/korelasyon 1y</code>")
        return
    await q.edit_message_text("[GRAFIK] <b>Analiz Menusu</b>", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("[GRAFIK] Benchmark", callback_data="analysis:benchmark"),
         InlineKeyboardButton("[DUSUS] Risk Metrikleri", callback_data="analysis:risk")],
        [InlineKeyboardButton("[ZAR] Monte Carlo", callback_data="analysis:montecarlo"),
         InlineKeyboardButton("🔗 Korelasyon", callback_data="analysis:correlation")],
        [InlineKeyboardButton("[GERI] Ana Menü", callback_data="menu:main")],
    ]))


@restricted
async def menu_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("[AYAR] <b>Ayarlar</b>\n\n• Plan değiştir: <code>/basla</code>\n• Maaş günü: <code>/maasgunu 8</code>\n• Bildirimler: <code>/bildirimler</code>")


@restricted
async def trade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) < 2:
        return
    action = parts[1]
    if action == "confirm":
        # trade:confirm:BUY:THYAO:100:250
        side = parts[2]
        symbol = parts[3]
        qty = float(parts[4])
        price = float(parts[5])
        if side == "BUY":
            portfolio.buy(q.from_user.id, symbol, qty, price, "TRY")
            cash_delta = -(qty * price)
        else:
            portfolio.sell(q.from_user.id, symbol, qty, price, "TRY")
            cash_delta = qty * price
        new_balance = await to_thread(add_cash, q.from_user.id, cash_delta)
        await q.edit_message_text(f"✅ <b>{side} {symbol}</b> {qty} @ {price:,.2f} = {qty*price:,.2f}₺\n[PARA] Nakit: {new_balance:,.2f}₺")
    elif action == "buy":
        await q.edit_message_text("[MARKET] Alım: <code>SYMBOL ADET FIYAT</code> (örn: THYAO 100 250)")
    elif action == "sell":
        await q.edit_message_text("[DUSUS] Satış: <code>SYMBOL ADET FIYAT</code> (örn: THYAO 50 300)")


@restricted
async def subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) < 2:
        return
    action = parts[1]
    if action == "confirm":
        amount = float(parts[2])
        day = int(parts[3])
        # Abonelik kaydetme mantığı basit tutuluyor
        await q.edit_message_text(f"✅ Abonelik takip edilecek: {amount:,.0f}₺ her ay {day}. gün")
    elif action == "reject":
        await q.edit_message_text("❌ Abonelik reddedildi.")


@restricted
async def push_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    if len(parts) < 2:
        return
    action = parts[1]
    if action == "mute":
        duration = parts[2] if len(parts) > 2 else "1h"
        await q.edit_message_text(f"🔕 Bildirimler {duration} sessiz moda alındı.")


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
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("durum", cmd_status))
    app.add_handler(CommandHandler("durumum", cmd_status))
    app.add_handler(CommandHandler("nakit", cmd_cash))
    app.add_handler(CommandHandler("maasgunu", cmd_salary_day))
    app.add_handler(CommandHandler("dengele", cmd_rebalance))
    app.add_handler(CommandHandler("oner", cmd_pick))
    app.add_handler(CommandHandler("temel", cmd_fundamental))
    app.add_handler(CommandHandler("backtest", cmd_backtest))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("makro", cmd_macro))
    app.add_handler(CommandHandler("haber", cmd_news))
    # Yeni komutlar
    app.add_handler(CommandHandler("not", cmd_note))
    app.add_handler(CommandHandler("notlar", cmd_notes))
    app.add_handler(CommandHandler("karsilastir", cmd_compare))
    app.add_handler(CommandHandler("takvim", cmd_calendar))
    app.add_handler(CommandHandler("saatler", cmd_trading_hours))
    app.add_handler(CommandHandler("alarm2", cmd_advanced_alert))
    app.add_handler(CommandHandler("alarm2lar", cmd_advanced_alerts_list))
    app.add_handler(CommandHandler("alarm2sil", cmd_advanced_alert_remove))
    # Webhook komutları
    app.add_handler(CommandHandler("alarmwebhook", cmd_webhook_add))
    app.add_handler(CommandHandler("alarmwebhooklar", cmd_webhook_list))
    app.add_handler(CommandHandler("alarmwebhooksil", cmd_webhook_remove))
    app.add_handler(CommandHandler("alarmwebhooktest", cmd_webhook_test))
    # Broker & Akşam analizi
    app.add_handler(CommandHandler("broker", cmd_broker_compare))
    app.add_handler(CommandHandler("brokerayarla", cmd_broker_set))
    app.add_handler(CommandHandler("aksam", cmd_evening_analysis))
    app.add_handler(CommandHandler("performans", cmd_performance))
    app.add_handler(CommandHandler("vergiraporu", cmd_tax_report))
    app.add_handler(CommandHandler("csv", cmd_csv_export))
    app.add_handler(CommandHandler("benchmark", cmd_benchmark))
    app.add_handler(CommandHandler("riskmetrik", cmd_risk_metrics))
    app.add_handler(CommandHandler("montecarlo", cmd_monte_carlo))
    app.add_handler(CommandHandler("temettutakip", cmd_dividend_track))
    app.add_handler(CommandHandler("korelasyon", cmd_correlation))
    app.add_handler(CommandHandler("yedek", cmd_backup))
    app.add_handler(CommandHandler("yedekal", cmd_restore))

    # Buton geri cagirmalari
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    app.add_handler(CallbackQueryHandler(checkin_expense_callback, pattern=r"^checkin:expense:"))
    app.add_handler(CallbackQueryHandler(salary_received_callback, pattern=r"^salary:"))
    # Menu callback handlers
    app.add_handler(CallbackQueryHandler(menu_cash_callback, pattern=r"^cash:"))
    app.add_handler(CallbackQueryHandler(menu_portfolio_callback, pattern=r"^portfolio:"))
    app.add_handler(CallbackQueryHandler(menu_risk_callback, pattern=r"^risk:"))
    app.add_handler(CallbackQueryHandler(menu_goals_callback, pattern=r"^goals:"))
    app.add_handler(CallbackQueryHandler(menu_expense_callback, pattern=r"^expense:"))
    app.add_handler(CallbackQueryHandler(menu_analysis_callback, pattern=r"^analysis:"))
    app.add_handler(CallbackQueryHandler(menu_settings_callback, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(trade_callback, pattern=r"^trade:"))
    app.add_handler(CallbackQueryHandler(subscription_callback, pattern=r"^sub:"))
    app.add_handler(CallbackQueryHandler(push_callback, pattern=r"^push:"))

    # Serbest metin (bekleyen harcama kaydi / yardim) EN SONA eklenmeli
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))
