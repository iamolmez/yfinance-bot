"""İşlem saatleri ve sinyal zamanlama analizi.

BIST, ABD, Kripto piyasaları için optimum işlem saatleri ve
saatlik sinyal kalitesi analizi.
"""
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional

from services.market_data import TZ_ISTANBUL, kind_of, md


@dataclass
class TradingSession:
    """İşlem oturumu bilgisi."""
    name: str
    market: str
    start: dtime
    end: dtime
    timezone: str
    characteristics: str


# Piyasa işlem saatleri (Türkiye saati bazında)
TRADING_SESSIONS = {
    "bist": TradingSession(
        name="BIST Ana Oturum",
        market="bist",
        start=dtime(9, 30),
        end=dtime(17, 50),
        timezone="Europe/Istanbul",
        characteristics="En yüksek hacim: 09:30-11:00 ve 16:00-17:50. Açılış/kapanış volatilitesi yüksek."
    ),
    "bist_pre": TradingSession(
        name="BIST Ön Seans",
        market="bist",
        start=dtime(9, 0),
        end=dtime(9, 30),
        timezone="Europe/Istanbul",
        characteristics="Emir toplama aşaması. Gerçek işlemler 09:30'dan başlar."
    ),
    "us_regular": TradingSession(
        name="ABD Normal Seans",
        market="us",
        start=dtime(16, 30),
        end=dtime(23, 0),
        timezone="Europe/Istanbul",
        characteristics="En yüksek likidite: 16:30-18:00 (Açılış) ve 21:30-23:00 (Kapanış). Veri açıklamaları 15:30-16:30."
    ),
    "us_pre": TradingSession(
        name="ABD Ön Piyasa",
        market="us",
        start=dtime(11, 0),
        end=dtime(16, 30),
        timezone="Europe/Istanbul",
        characteristics="Düşük hacim, geniş spread. Sadece limit emir önerilir."
    ),
    "us_after": TradingSession(
        name="ABD Kapanış Sonrası",
        market="us",
        start=dtime(23, 0),
        end=dtime(3, 0),
        timezone="Europe/Istanbul",
        characteristics="Düşük likidite. Bilanço açıklamaları sonrası hareketler olabilir."
    ),
    "crypto": TradingSession(
        name="Kripto 7/24",
        market="crypto",
        start=dtime(0, 0),
        end=dtime(23, 59),
        timezone="UTC",
        characteristics="Asya (02:00-10:00), Avrupa (10:00-18:00), ABD (15:00-23:00) saatlerinde hacim artar. Hafta sonu da işlem görür."
    ),
}


# Saatlik sinyal kalitesi skorları (0-100)
# BIST için
BIST_HOURLY_QUALITY = {
    9: 60,   # Açılış - volatil, yön belirsiz
    10: 85,  # Stabilleşme - trend netleşir
    11: 80,
    12: 70,  # Ara öğle - hacim düşer
    13: 65,
    14: 75,  # Öğleden sonra - hacim artar
    15: 85,
    16: 90,  # Kapanış öncesi - en güçlü sinyaller
    17: 80,
    18: 50,  # Kapanış - manipülasyon riski
}

# ABD için (TR saati)
US_HOURLY_QUALITY = {
    16: 70,  # Pre-market sonrası
    17: 85,  # Açılış (16:30 NY = 23:30 TR yaz, 22:30 TR kış) -> yaklaşık 17:00 TR
    18: 90,  # Açılış sonrası güçlü trend
    19: 85,
    20: 80,
    21: 85,  # ABD öğleden sonra
    22: 90,  # Kapanış öncesi (21:30 NY = 04:30 TR yaz)
    23: 75,
}

# Kripto için (TR saati)
CRYPTO_HOURLY_QUALITY = {
    2: 70,   # Asya açılışı
    3: 75,
    4: 80,
    5: 85,
    6: 80,
    7: 75,
    8: 70,
    9: 75,   # Avrupa açılışı
    10: 85,
    11: 85,
    12: 80,
    13: 75,
    14: 80,  # ABD ön piyasa
    15: 85,  # ABD açılışı yaklaşıyor
    16: 90,  # ABD açılışı (16:30 NY = 23:30 TR)
    17: 85,
    18: 80,
    19: 75,
    20: 70,
    21: 65,
    22: 60,
    23: 65,
    0: 70,
    1: 75,
}


def get_current_session(symbol: str) -> Optional[TradingSession]:
    """Sembol için şu anki aktif oturumu döndürür."""
    k = kind_of(symbol)
    now = datetime.now(TZ_ISTANBUL).time()
    
    if k == "bist":
        for key in ["bist_pre", "bist"]:
            sess = TRADING_SESSIONS[key]
            if sess.start <= now <= sess.end:
                return sess
    elif k == "us":
        for key in ["us_pre", "us_regular", "us_after"]:
            sess = TRADING_SESSIONS[key]
            if sess.start <= now <= sess.end:
                return sess
    elif k == "crypto":
        return TRADING_SESSIONS["crypto"]
    
    return None


def get_next_session(symbol: str) -> Optional[TradingSession]:
    """Sembol için bir sonraki oturumu döndürür."""
    k = kind_of(symbol)
    now = datetime.now(TZ_ISTANBUL).time()
    
    sessions = []
    if k == "bist":
        sessions = ["bist_pre", "bist"]
    elif k == "us":
        sessions = ["us_pre", "us_regular", "us_after"]
    elif k == "crypto":
        return TRADING_SESSIONS["crypto"]
    
    for key in sessions:
        sess = TRADING_SESSIONS[key]
        if now < sess.start:
            return sess
    
    # Yarınki ilk oturum
    if sessions:
        return TRADING_SESSIONS[sessions[0]]
    return None


def get_hourly_quality(symbol: str, hour: Optional[int] = None) -> int:
    """Belirli saat için sinyal kalite skoru (0-100)."""
    if hour is None:
        hour = datetime.now(TZ_ISTANBUL).hour
    
    k = kind_of(symbol)
    if k == "bist":
        return BIST_HOURLY_QUALITY.get(hour, 50)
    elif k == "us":
        return US_HOURLY_QUALITY.get(hour, 50)
    elif k == "crypto":
        return CRYPTO_HOURLY_QUALITY.get(hour, 70)
    return 50


def get_trading_hours_advice(symbol: str) -> str:
    """Sembol için işlem saati tavsiyesi üretir."""
    k = kind_of(symbol)
    now = datetime.now(TZ_ISTANBUL)
    current_hour = now.hour
    current_time = now.time()
    
    current_session = get_current_session(symbol)
    next_session = get_next_session(symbol)
    quality = get_hourly_quality(symbol, current_hour)
    
    lines = [
        f"🕐 <b>{symbol} — İşlem Saati Analizi</b>",
        f"📅 {now:%d %B %Y, %A} | 🕐 {now:%H:%M} (TR)",
        "",
    ]
    
    if current_session:
        lines.append(f"✅ <b>Aktif Oturum:</b> {current_session.name}")
        lines.append(f"   ⏰ {current_session.start:%H:%M} - {current_session.end:%H:%M}")
        lines.append(f"   📝 {current_session.characteristics}")
        lines.append("")
    else:
        lines.append("🔴 <b>Piyasa Kapalı</b>")
        if next_session:
            lines.append(f"📅 Sonraki oturum: {next_session.name} ({next_session.start:%H:%M})")
        lines.append("")
    
    # Kalite skoru
    if quality >= 80:
        quality_emoji = "🟢"
        quality_text = "Mükemmel - Sinyaller çok güvenilir"
    elif quality >= 70:
        quality_emoji = "🟡"
        quality_text = "İyi - Sinyaller güvenilir"
    elif quality >= 60:
        quality_emoji = "🟠"
        quality_text = "Orta - Dikkatli ol"
    else:
        quality_emoji = "🔴"
        quality_text = "Zayıf - İşlemden kaçın"
    
    lines.append(f"{quality_emoji} <b>Bu Saat Sinyal Kalitesi: %{quality}</b>")
    lines.append(f"   {quality_text}")
    lines.append("")
    
    # Saatlik öneri
    if k == "bist":
        if 9 <= current_hour <= 10:
            lines.append("💡 <b>Öneri:</b> Açılık volatilitesi yüksek. 10:00 sonrası trend netleşene kadar bekle.")
        elif 15 <= current_hour <= 17:
            lines.append("💡 <b>Öneri:</b> Kapanışा öncesi en güçlü sinyaller. Pozisyon alım/satım için uygun.")
        elif current_hour == 17 or current_hour == 18:
            lines.append("⚠️ <b>Uyarı:</b> Kapanış manipülasyonu riski. Sadece limit emir kullan.")
        elif current_hour < 9 or current_hour > 18:
            lines.append("💤 Piyasa kapalı. Yarın 09:30'dan sonra işlem yap.")
    
    elif k == "us":
        # TR saatinde ABD saatleri: Yaz 16:30-23:00, Kış 17:30-00:00
        if 16 <= current_hour <= 18:
            lines.append("💡 <b>Öneri:</b> ABD açılışı (yaklaşık 16:30-18:00 TR). En yüksek hacim ve trend oluşumu.")
        elif 21 <= current_hour <= 23:
            lines.append("💡 <b>Öneri:</b> ABD kapanışı yaklaşıyor (23:00 TR). Gün içi trendler netleşir.")
        elif current_hour < 16 or current_hour > 23:
            lines.append("💤 ABD piyasası kapalı/pre-market. Sadece limit emir önerilir.")
    
    elif k == "crypto":
        if 2 <= current_hour <= 10:
            lines.append("💡 <b>Öneri:</b> Asya seansı aktif. BTC/ETH hacmi artar.")
        elif 14 <= current_hour <= 23:
            lines.append("💡 <b>Öneri:</b> ABD seansı aktif. En yüksek likidite ve fiyat keşfi.")
    
    lines.append("")
    lines.append("⚠️ <i>Bu analiz geçmiş verilere dayanır, garanti vermez.</i>")
    
    return "\n".join(lines)


def get_weekly_schedule() -> str:
    """Haftalık işlem programı özeti."""
    lines = [
        "📅 <b>Haftalık İşlem Programı (TR Saati)</b>",
        "",
        "<b>Pazartesi - Cuma:</b>",
        "  🇹🇷 BIST: 09:30 - 17:50",
        "  🇺🇸 ABD (Yaz): 16:30 - 23:00",
        "  🇺🇸 ABD (Kış): 17:30 - 00:00",
        "  🪙 Kripto: 7/24",
        "",
        "<b>Pazar - Pazartesi (Gece):</b>",
        "  🇺🇸 ABD: Kapalı (Kripto açık)",
        "  🇹🇷 BIST: Kapalı",
        "",
        "<b>Önemli Saatler:</b>",
        "  📊 10:00-11:00  → BIST trend netleşir",
        "  📊 15:30-16:30  → ABD veri açıklamaları (CPI, Fed, İşsizlik)",
        "  📊 16:30-18:00  → ABD açılışı (en yüksek hacim)",
        "  📊 15:00-17:00  → BIST kapanış öncesi",
        "  📊 21:30-23:00  → ABD kapanışı (gün sonu trend)",
        "",
        "⚠️ <i>Yaz/Kış saati farkı için ABD saatleri değişir.</i>",
    ]
    return "\n".join(lines)