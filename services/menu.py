"""Inline Keyboard Menu Sistemi - Tum islemler butonla."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Ana menu - her zaman en ust seviye."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("[PARA] Nakit", callback_data="menu:cash"),
         InlineKeyboardButton("[ARTIS] Portfoy", callback_data="menu:portfolio")],
        [InlineKeyboardButton("[KALKAN] Risk", callback_data="menu:risk"),
         InlineKeyboardButton("[HEDEF] Hedefler", callback_data="menu:goals")],
        [InlineKeyboardButton("[HARCAMA] Harcama", callback_data="menu:expense"),
         InlineKeyboardButton("[GRAFIK] Analiz", callback_data="menu:analysis")],
        [InlineKeyboardButton("[AYAR] Ayarlar", callback_data="menu:settings"),
         InlineKeyboardButton("ℹ️ Yardim", callback_data="menu:help")],
    ])


def cash_menu(balance: float) -> InlineKeyboardMarkup:
    """Nakit menusu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"[PARA] Bakiye: {balance:,.0f}₺", callback_data="noop")],
        [InlineKeyboardButton("➕ Para Ekle", callback_data="cash:add"),
         InlineKeyboardButton("➖ Para Cikar", callback_data="cash:remove")],
        [InlineKeyboardButton("[GRAFIK] Detay", callback_data="cash:detail"),
         InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")],
    ])


def portfolio_menu(total: float, positions: int) -> InlineKeyboardMarkup:
    """Portfoy menusu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"[ARTIS] Deger: {total:,.0f}₺ ({positions} pozisyon)", callback_data="noop")],
        [InlineKeyboardButton("🔄 Dengele", callback_data="portfolio:rebalance"),
         InlineKeyboardButton("[HEDEF] Oneriler", callback_data="portfolio:pick")],
        [InlineKeyboardButton("[MARKET] Al", callback_data="trade:buy"),
         InlineKeyboardButton("[DUSUS] Sat", callback_data="trade:sell")],
        [InlineKeyboardButton("[GRAFIK] Detay", callback_data="portfolio:detail"),
         InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")],
    ])


def risk_menu(score: int, level: str) -> InlineKeyboardMarkup:
    """Risk menusu - gorsel cubuk."""
    bar = "█" * score + "░" * (10 - score)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"[KALKAN] Risk: {score}/10 {level}", callback_data="noop")],
        [InlineKeyboardButton(f"{bar}", callback_data="noop")],
        [InlineKeyboardButton("[AYAR] Risk Ayarla", callback_data="risk:set"),
         InlineKeyboardButton("[GRAFIK] Detay", callback_data="risk:detail")],
        [InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")],
    ])


def goals_menu(invest_progress: float, emergency_progress: float) -> InlineKeyboardMarkup:
    """Hedefler menusu - gorsel cubuklar."""
    inv_bar = "█" * int(invest_progress / 10) + "░" * (10 - int(invest_progress / 10))
    emg_bar = "█" * int(emergency_progress / 10) + "░" * (10 - int(emergency_progress / 10))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"[HEDEF] Yatirim: {inv_bar} %{invest_progress:.0f}", callback_data="noop")],
        [InlineKeyboardButton(f"[KALKAN] Acil Fon: {emg_bar} %{emergency_progress:.0f}", callback_data="noop")],
        [InlineKeyboardButton("[HEDEF] Hedef Degistir", callback_data="goals:set"),
         InlineKeyboardButton("[GRAFIK] Detay", callback_data="goals:detail")],
        [InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")],
    ])


def expense_menu() -> InlineKeyboardMarkup:
    """Harcama menusu - hizli kategori butonlari."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("[MARKET] Market", callback_data="expense:cat:market"),
         InlineKeyboardButton("[BENZIN] Ulasim", callback_data="expense:cat:transport")],
        [InlineKeyboardButton("[YEMEK] Yemek", callback_data="expense:cat:food"),
         InlineKeyboardButton("[SAGLIK] Saglik", callback_data="expense:cat:health")],
        [InlineKeyboardButton("[EGLENCE] Eglence", callback_data="expense:cat:entertainment"),
         InlineKeyboardButton("[DIGER] Diger", callback_data="expense:cat:other")],
        [InlineKeyboardButton("[OZEL] Ozel", callback_data="expense:custom"),
         InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")],
    ])


def trade_confirm_menu(symbol: str, side: str, qty: float, price: float) -> InlineKeyboardMarkup:
    """Al/Sat onay menusu."""
    action = "AL" if side == "BUY" else "SAT"
    emoji = "🟢" if side == "BUY" else "🔴"
    total = qty * price
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{emoji} {action} {symbol} {qty:.4f} @ {price:,.2f} = {total:,.2f}₺", callback_data="noop")],
        [InlineKeyboardButton("[TIK] Onayla", callback_data=f"trade:confirm:{side}:{symbol}:{qty}:{price}"),
         InlineKeyboardButton("[CARPI] Iptal", callback_data="menu:portfolio")],
    ])


def expense_confirm_menu(amount: float, category: str) -> InlineKeyboardMarkup:
    """Harcama onay menusu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"[HARCAMA] {amount:,.0f}₺ → {category.title()}", callback_data="noop")],
        [InlineKeyboardButton("[TIK] Kaydet", callback_data=f"expense:confirm:{amount}:{category}"),
         InlineKeyboardButton("[CARPI] Iptal", callback_data="menu:expense")],
    ])


def smart_category_suggestions(text: str) -> InlineKeyboardMarkup:
    """Akilli kategori onerileri - metin analiz sonrasi."""
    text_lower = text.lower()
    suggestions = []

    if any(w in text_lower for w in ["market", "bim", "a101", "migros", "sok", "carrefour"]):
        suggestions.append(("[MARKET] Market", "expense:cat:market"))
    if any(w in text_lower for w in ["benzin", "shell", "bp", "opo", "petrol", "gaz"]):
        suggestions.append(("[BENZIN] Ulasim", "expense:cat:transport"))
    if any(w in text_lower for w in ["yemek", "restoran", "cafe", "kahve", "mcdonalds", "burger"]):
        suggestions.append(("[YEMEK] Yemek", "expense:cat:food"))
    if any(w in text_lower for w in ["eczane", "ilac", "hastane", "doktor", "saglik"]):
        suggestions.append(("[SAGLIK] Saglik", "expense:cat:health"))
    if any(w in text_lower for w in ["sinema", "netflix", "spotify", "oyun", "steam", "eglence"]):
        suggestions.append(("[EGLENCE] Eglence", "expense:cat:entertainment"))

    if not suggestions:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("[DIGER] Diger", callback_data="expense:cat:other"),
            InlineKeyboardButton("[OZEL] Kendi Gir", callback_data="expense:custom")
        ], [
            InlineKeyboardButton("[GERI] Iptal", callback_data="menu:expense")
        ]])

    rows = []
    for i in range(0, len(suggestions), 2):
        row = [InlineKeyboardButton(s[0], callback_data=s[1]) for s in suggestions[i:i+2]]
        rows.append(row)
    rows.append([InlineKeyboardButton("[DIGER] Diger", callback_data="expense:cat:other"),
                 InlineKeyboardButton("[OZEL] Kendi Gir", callback_data="expense:custom")])
    rows.append([InlineKeyboardButton("[GERI] Iptal", callback_data="menu:expense")])
    return InlineKeyboardMarkup(rows)


def subscription_detected_menu(name: str, amount: float, day: int) -> InlineKeyboardMarkup:
    """Abonelik tespit edildi menusu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔄 Abonelik tespit edildi: {name} {amount:,.0f}₺/ay (her ay {day})", callback_data="noop")],
        [InlineKeyboardButton("[TIK] Dogru, Takip Et", callback_data=f"sub:confirm:{amount}:{day}"),
         InlineKeyboardButton("[CARPI] Yanlis", callback_data="sub:reject")],
    ])


def proactive_push_buttons(context: str) -> InlineKeyboardMarkup:
    """Proaktif push butonlari - baglama gore."""
    buttons = {
        "price_drop": [
            [InlineKeyboardButton("[GRAFIK] Analiz Et", callback_data="analysis:THYAO"),
             InlineKeyboardButton("[MARKET] Alim Yap", callback_data="trade:buy:THYAO")],
            [InlineKeyboardButton("🔕 Sessiz Mod", callback_data="push:mute:1h")],
        ],
        "goal_progress": [
            [InlineKeyboardButton("[HEDEF] Hedef Detay", callback_data="menu:goals"),
             InlineKeyboardButton("[GRAFIK] Portfoy", callback_data="menu:portfolio")],
        ],
        "risk_alert": [
            [InlineKeyboardButton("[KALKAN] Risk Kontrol", callback_data="menu:risk"),
             InlineKeyboardButton("🛑 Stop-Loss Kontrol", callback_data="risk:stoploss")],
            [InlineKeyboardButton("🔕 1 Saat Sessiz", callback_data="push:mute:1h")],
        ],
        "daily_summary": [
            [InlineKeyboardButton("[GRAFIK] Detay", callback_data="menu:portfolio"),
             InlineKeyboardButton("[HARCAMA] Harcama Gir", callback_data="menu:expense")],
            [InlineKeyboardButton("🔕 Yarin Sessiz", callback_data="push:mute:24h")],
        ],
    }
    return InlineKeyboardMarkup(buttons.get(context, [[InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")]]))