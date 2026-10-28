"""Otonom finans asistani.

Kullaniciyi karmasik yatirim terimlerinden uzak tutar:
- Maaşi otomatik boler (zorunlu / istege bagli / birikim)
- Risk profilini baz alarak BASIT yatirim dagilimi onerir
- Sade dille gunluk yonlendirme yapar
"""
import json
from datetime import datetime

from services.market_data import TZ_ISTANBUL

RISK_LABELS = {
    "sakin": "🛡️ Sakin (düşük risk)",
    "dengeli": "⚖️ Dengeli (orta risk)",
    "atilgan": "🚀 Atılgan (yüksek risk)",
}

GOAL_LABELS = {
    "acil_fon": "🆘 Acil durum fonu",
    "buyuk_hedef": "🏠 Ev / araba / büyük hedef",
    "emeklilik": "👵 Emeklilik / uzun vade",
    "kisa_vade": "⚡ Kısa vadede kazanç",
}

# Risk profiline gore BASIT dagilim onerileri (isim, yuzde)
_RISK_ALLOC = {
    "sakin": [
        ("🥇 Altın", 40),
        ("💵 Döviz (USD)", 30),
        ("📊 BIST endeks (XU100)", 30),
    ],
    "dengeli": [
        ("📊 BIST endeks + büyük hisseler", 50),
        ("🥇 Altın", 30),
        ("💵 Döviz / nakit", 20),
    ],
    "atilgan": [
        ("📈 Hisse senetleri (BIST + ABD)", 60),
        ("🥇 Altın", 15),
        ("🪙 Kripto (en fazla %15)", 15),
        ("💵 Nakit / döviz", 10),
    ],
}

TIPS = [
    "Önce kendine öde: Gelirinin en az %20'sini maaşın geldiği gün bir kenara ayır.",
    "Acil durum fonu: 3-6 aylık giderini karşılayacak nakdi önce biriktir. Bu senin uyku ilacın.",
    "Tek hisseye yatırma. Birden fazla varlığa bölmek riski azaltır (çeşitlendirme).",
    "Piyasa düştüğünde panik yapma. Düzenli yatırım yapıyorsan düşüşler senin için indirimdir.",
    "Kısa vade kumar gibidir, uzun vade yatırımdır. Sabır en büyük avantajındır.",
    "Kaldıraçlı işlemlerden (forex, vadeli) uzak dur. Kaybını katlayabilirsin.",
    "Her ay aynı gün aynı tutarı yatır (dolar maliyet ortalaması). Zamanlama derdi olmaz.",
    "Borçla yatırım yapma. Önce kredi kartı borcunu kapat, sonra yatır.",
    "Anlamadığın hiçbir şeye para koyma. 'Çok kazandırır' diyenlere şüpheyle yaklaş.",
    "Giderlerini takip etmek, maaşını artırmaktan kolaydır. Her harcamayı kaydet.",
    "Altın uzun vadede değerini korur ama tek başına zengin etmez. Portföyün bir parçası olsun.",
    "Kriptoda toplam portföyünün en fazla %10-15'ini riske at. Gerisi sabit kalsın.",
    "Yatırım kararlarını akşam değil, sakin kafayla ver. Panik satışı en pahalı hatadır.",
    "BIST'te işlem saatleri hafta içi 09:00-18:00. Bu saatler dışında emir veremezsin.",
    "Uzun vadede endeks (XU100) çoğu bireysel hisse seçiminden daha iyi sonuç verir.",
]


def build_plan(salary: float, expenses: float, risk: str, goal: str,
               salary_day: int) -> dict:
    """50/30/20 kurali + kisisel ayarlamalarla maas dagilimi uretir."""
    salary = max(salary, 0.0)
    expenses = min(max(expenses, 0.0), salary)

    needs = expenses                      # zorunlu giderler
    wants = salary * 0.30                 # istege bagli
    savings = salary - needs - wants      # birikim + yatirim

    warning = None
    if savings < salary * 0.10:
        # Giderler cok yuksek: istege bagliyi asgariye cek
        wants = salary * 0.10
        savings = max(salary - needs - wants, 0.0)
        warning = ("Giderlerin maaşının %50'sinden fazla. İsteğe bağlı harcamayı "
                   "minimuma çektim ama önceliğin giderlerini kısmak olmalı.")
    if needs > salary * 0.50:
        warning = ("Giderlerin maaşının yarısından fazla. Birikim yapabilmen için "
                   "giderlerini kısman şart. İlk hedefin bu olmalı.")

    emergency_target = expenses * 6  # 6 aylik guvenlik agi
    emergency_share = savings * (0.5 if goal == "acil_fon" else 0.3)
    invest_share = max(savings - emergency_share, 0.0)

    suggestions = [
        {"name": name, "pct": pct, "amount": round(invest_share * pct / 100, 2)}
        for name, pct in _RISK_ALLOC[risk]
    ]

    return {
        "salary": round(salary, 2),
        "expenses": round(expenses, 2),
        "risk": risk,
        "goal": goal,
        "salary_day": salary_day,
        "needs": round(needs, 2),
        "wants": round(wants, 2),
        "savings": round(savings, 2),
        "emergency_target": round(emergency_target, 2),
        "emergency_share": round(emergency_share, 2),
        "invest_share": round(invest_share, 2),
        "suggestions": suggestions,
        "warning": warning,
    }


def describe_plan(p: dict, saved: float = 0.0) -> str:
    """Plani sade dille anlatan mesaj."""
    lines = [
        "📋 <b>Senin Planın</b>",
        f"💰 Maaş: {_fmt(p['salary'])}",
        f"📆 Maaş günü: ayın {p['salary_day']}. günü",
        "",
        "<b>💸 Maaşın nasıl bölünüyor?</b>",
        f"🏠 Zorunlu giderler: <b>{_fmt(p['needs'])}</b>",
        f"🎉 İsteğe bağlı harcama: <b>{_fmt(p['wants'])}</b>",
        f"💾 Birikim + yatırım: <b>{_fmt(p['savings'])}</b>",
        "",
        "<b>🛡️ Acil durum fonu</b>",
        f"🎯 Hedef: {_fmt(p['emergency_target'])} (6 aylık giderin)",
        f"📌 Her ay: {_fmt(p['emergency_share'])} biriktirilecek",
        f"✅ Şu ana kadar: {_fmt(saved)}",
    ]
    if p["invest_share"] > 0:
        lines += [
            "",
            "<b>📈 Yatırım dağılımı</b> (aylık: " + _fmt(p["invest_share"]) + ")",
        ]
        for s in p["suggestions"]:
            lines.append(f"• {s['name']}: %{s['pct']} ({_fmt(s['amount'])})")
    else:
        lines += ["", "⚠️ Birikim için ayırabilecek pay kalmadı. Giderlerini kıs."]
    if p.get("warning"):
        lines += ["", f"⚠️ <b>Uyarı:</b> {p['warning']}"]
    lines += ["", "🛠️ İşlem kaydı: /ekle SYMBOL ADET FIYAT",
              "💡 Bilgi istersen: /asistan"]
    return "\n".join(lines)


def tip_of_day(offset: int = 0) -> str:
    day = datetime.now(TZ_ISTANBUL).toordinal() + offset
    return TIPS[day % len(TIPS)]


def emergency_status(p: dict, saved: float) -> str:
    if p["emergency_target"] <= 0:
        return "Acil durum fonu hedefi tanımlı değil."
    pct = saved / p["emergency_target"] * 100
    bar_len = 12
    filled = max(0, min(bar_len, int(pct / 100 * bar_len)))
    bar = "█" * filled + "░" * (bar_len - filled)
    return f"🛡️ Acil durum fonu: %{pct:.0f} {bar} ({_fmt(saved)} / {_fmt(p['emergency_target'])})"


def simple_signal_hint(sig: dict | None) -> str:
    """Bir sinyali korkutmadan, sade dille anlatir."""
    if not sig:
        return ""
    s = sig
    msg = {
        "GÜÇLÜ AL": "bugün teknik göstergelere göre <b>oldukça ucuz</b> görünüyor. Ama acele etme, planına uygun yatırım payınla al.",
        "AL": "teknik göstergelere göre <b>makul fiyatlı</b> görünüyor.",
        "HAFİF AL": "fiyatı hafif düşük görünüyor, yakından izlemeye değer.",
        "NÖTR": "ne pahalı ne ucuz, normal seviyede.",
        "HAFİF SAT": "biraz pahalanmış görünüyor, satmayı düşünme ama yeni alım yapma.",
        "SAT": "teknik göstergelere göre <b>pahalı</b> görünüyor.",
        "GÜÇLÜ SAT": "aşırı pahalanmış görünüyor, karını almayı düşünebilirsin.",
    }.get(s["signal"], "normal seviyede.")
    return f"🔍 {s['symbol']} {msg}"


def today_action(plan: dict | None, saved: float, invested_month: float,
                 invest_target: float) -> str:
    """Bugun ne yapilmali - sade bir oneri."""
    if not plan:
        return ("📋 Planın henüz yok. 2 dakikada oluşturmak için: <code>/basla</code>\n"
                "Böylece sana ne kadar biriktirip nasıl yatırım yapman gerektiğini söyleyebilirim.")
    lines = ["📌 <b>Bugün için önerim:</b>"]
    if saved < plan["emergency_target"]:
        lines.append(f"🛡️ Acil durum fonuna {_fmt(plan['emergency_share'])} ₺ ayırmaya devam et. "
                     f"(%{saved / plan['emergency_target'] * 100:.0f} tamamlandı)")
    if plan["invest_share"] > 0:
        remaining = max(invest_target - invested_month, 0)
        if remaining > 0:
            lines.append(f"📈 Bu ay yatırım hedefine {_fmt(remaining)} ₺ kaldı. "
                         "Hisselerden birine ekleyebilirsin: /sinyal")
        else:
            lines.append("🎉 Bu ayın yatırım hedefini tamamladın. Planına sadık kaldın!")
    lines.append(f"🧾 Bugün yapılan harcamaları akşam kontrolünde bana bildir.")
    return "\n".join(lines)


def _fmt(v: float) -> str:
    return f"{v:,.2f} ₺"


def plan_to_json(p: dict) -> str:
    return json.dumps(p, ensure_ascii=False)


def plan_from_json(raw: str) -> dict:
    return json.loads(raw)
