"""Dogal dil komut cozumleyici (LLM gerektirmez).

Kullanici normal Turkce yazar -> anahtar kelime eslesmesi ile niyet cikarilir.

Ornekler:
  "BTC ne durumda?"        -> {"action": "price", "symbol": "BTC-USD"}
  "THYAO alınır mı?"       -> {"action": "signal", "symbol": "THYAO.IS"}
  "bu ay ne kadar harcadım"-> {"action": "expense"}
  "portföyüm nasıl?"       -> {"action": "portfolio"}
  "ne almalıyım?"          -> {"action": "signals"}
  "bana bir şey öğret"     -> {"action": "tip"}
  "planımı göster"         -> {"action": "plan"}
  "durumum ne"             -> {"action": "status"}
  "akşam analizi yap"      -> {"action": "evening"}
  "broker karşılaştır THYAO" -> {"action": "broker", "symbol": "THYAO.IS"}
  "broker ayarla midas"   -> {"action": "broker_set", "broker": "midas"}
  "saatler THYAO"          -> {"action": "hours", "symbol": "THYAO.IS"}
  "hangi saatte almalıyım" -> {"action": "hours"}
"""
import re

from services import market_data as md

# Yuksek oncelikli niyet anahtar kelimeleri (sembolden once kontrol edilir)
_STRONG = {
    "expense": ["harcad", "harcama", "masraf", "gider", "kalan", "butcem", "bütçem", "bütçe"],
    "cash": ["nakit", "eldeki para", "ne kadar param", "ne kadar para", "bankada", "hesabımda"],
    "pick": ["sen seç", "sen sec", "otomatik seç", "otomatik sec", "kendin seç", "kendin sec", "bana hisse öner", "bana hisse oner", "hisse öner", "hisse oner", "ne alsam", "ne alayım sen seç", "sen karar ver"],
    "rebalance": ["dengele", "ne alayım ne satayım", "ne alayim ne satayim", "al sat", "dağılımı dengele", "dagilimi dengele", "ne alıp ne satayım", "ne alip ne satayim"],
    "portfolio": ["portfoy", "portföy", "hisse senedim", "yatırımım", "varlıklarım", "servetim", "param ne kadar"],
    "plan": ["planım", "planımı", "plan", "maaş", "maas", "dagilim", "dağılım"],
    "tip": ["ogret", "öğret", "bilgi ver", "ipucu", "eğitim", "egitim", "bilgilendir", "öğren", "ders ver"],
    "status": ["durumum", "genel durum", "özet çıkar", "ozet cikar", "rapor çıkar"],
    "makro": ["makro", "dolar ne durumda", "piyasa nasıl", "piyasa genel", "kur ne", "kurlar", "endeksler", "genel piyasa"],
    "risk": ["risk analizi", "riskim", "riskli mi", "portföy riski", "çeşitlendirme", "cesitlendirme"],
    "backtest": ["backtest", "geriye dönük", "geçmiş test", "gecti mi", "kazandırır mı"],
    "news": ["haber", "son haber", "gündem", "ne var haberlerde"],
    "temel": ["temel analiz", "temel veri", "finansal", "şirket değeri", "sirket degeri", "f/k", "fk ne"],
    "signals": ["sinyal", "alınır mı", "alinir mi", "alınmalı", "firsat", "fırsat", "ne almalıyım", "öneri", "oneri", "tavsiye", "hisse öner"],
    "evening": ["akşam analizi", "aksam analizi", "akşam rapor", "aksam rapor", "bugün ne yapmalı", "bugun ne yapmali", "satmalı mı", "satmali mi", "almalı mı", "almalimi"],
    "broker": ["broker karşılaştır", "broker karsilastir", "hangi broker", "komisyon karşılaştır", "komisyon karsilastir", "ucuz broker", "en ucuz broker"],
    "broker_set": ["broker ayarla", "varsayılan broker", "varsayilan broker", "broker sec", "broker seç"],
    "hours": ["saatler", "hangi saatte", "ne zaman almalı", "ne zaman satmalı", "işlem saati", "islem saati", "piyasa açık mı", "piyasa acik mi", "en iyi saat"],
}

# Sembol aramasinda atlanacak yaygin kelimeler
_STOP = {
    "BUGUN", "BU", "AY", "MAAS", "MAAŞ", "PLAN", "PLANIM", "NE", "NASIL", "NEDİR",
    "KADAR", "YIL", "GUN", "GÜN", "HAFTA", "HISSE", "HİSSE", "ALINIR", "ALINMALI",
    "YATIRIM", "PARAM", "PORTFOY", "PORTFÖY", "SINYAL", "SİNYAL", "DURUM", "FIRSAT",
}

_SYMBOL_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ0-9]{2,8})\b")


def _find_symbol(text_upper: str) -> str | None:
    """Metindeki ilk cozulebilir sembolu bulur (onbellekli)."""
    for token in _SYMBOL_RE.findall(text_upper):
        if token in _STOP:
            continue
        if token in md.ALIASES:
            return md.ALIASES[token]
        # BIST / kripto / ABD tahmini icin cozmeyi dene
        try:
            resolved = md.resolve_symbol(token)
        except Exception:
            continue
        if resolved:
            return resolved[0]
    return None


def parse(text: str) -> dict:
    """Metni cozumler. {'action': ..., 'symbol': ..., 'broker': ...} dondurur."""
    low = text.lower()
    upper = text.upper()

    # 1) Guclu niyetler
    for action, kws in _STRONG.items():
        if any(kw in low for kw in kws):
            symbol = _find_symbol(upper) if action in ("signal", "signals", "broker", "hours") else None
            
            # broker_set için broker adını çıkar
            broker_name = None
            if action == "broker_set":
                for b in ["midas", "isyatirim", "garanti", "vakif", "deniz", "komisyonsuz_bist", "interactive_brokers"]:
                    if b in low:
                        broker_name = b
                        break
            
            if symbol and action == "signals":
                return {"action": "signal", "symbol": symbol}
            return {"action": action, "symbol": symbol, "broker": broker_name}

    # 2) Sembol varsa fiyat sorusu
    symbol = _find_symbol(upper)
    if symbol:
        return {"action": "price", "symbol": symbol}

    return {"action": None, "symbol": None, "broker": None}
