"""Portfoy risk analizi.

Konsantrasyon, cesitlendirme skoru, varlik sinifi dagilimi ve volatiliteyi
olcer. Sonuc sade dille anlatilir.
"""
from collections import defaultdict

import numpy as np

from services import assistant, market_data as md

_CLASS_LABELS = {
    "stocks": "📈 Hisse",
    "gold": "🥇 Altın",
    "cash": "💵 Döviz/nakit",
    "crypto": "🪙 Kripto",
}


def analyze(positions: list, cash: float = 0.0) -> dict:
    invested = sum(p.market_value for p in positions)
    total = invested + cash
    if total <= 0:
        return {"ok": False}

    weights = [p.market_value / invested for p in positions] if invested else []
    top_weight = max(weights) if weights else 0.0
    herf = sum(w * w for w in weights)
    diversification = round((1 - herf) * 100, 0)

    classes: dict[str, float] = defaultdict(float)
    for p in positions:
        classes[assistant.classify_symbol(p.symbol)] += p.market_value

    vols: list[float] = []
    for p in positions:
        df = md.get_history(p.symbol, period="3mo")
        if df is None or len(df) < 30:
            continue
        rets = df["Close"].pct_change().dropna()
        if len(rets) < 20:
            continue
        vols.append(float(rets.std() * np.sqrt(252) * 100))

    avg_vol = float(np.mean(vols)) if vols else None
    if avg_vol is None:
        risk_label = "Belirlenemedi"
    elif avg_vol < 25:
        risk_label = "Düşük 🟢"
    elif avg_vol < 40:
        risk_label = "Orta 🟡"
    elif avg_vol < 60:
        risk_label = "Yüksek 🟠"
    else:
        risk_label = "Çok yüksek 🔴"

    return {
        "ok": True,
        "total": total,
        "invested": invested,
        "cash": cash,
        "top_symbol": max(positions, key=lambda p: p.market_value).symbol if positions else "",
        "top_weight": top_weight * 100,
        "diversification": diversification,
        "classes": dict(classes),
        "avg_volatility": avg_vol,
        "risk_label": risk_label,
        "n_positions": len(positions),
    }


def risk_text(r: dict) -> str:
    if not r.get("ok"):
        return "Portföyün ve nakitin boş. Önce /nakit ve /ekle ile başla."

    lines = ["📉 <b>Portföy Risk Analizi</b>"]
    lines.append(f"🏦 Toplam: {r['total']:,.0f} ₺ ({r['n_positions']} pozisyon)")

    lines.append("")
    lines.append("<b>🎭 Varlık dağılımı</b>")
    if r["classes"]:
        for cls, val in sorted(r["classes"].items(), key=lambda x: -x[1]):
            pct = val / r["total"] * 100
            lines.append(f"• {_CLASS_LABELS.get(cls, cls)}: %{pct:.0f} ({val:,.0f} ₺)")
    if r["cash"] > 0:
        lines.append(f"• 💵 Nakit: %{r['cash']/r['total']*100:.0f} ({r['cash']:,.0f} ₺)")

    lines.append("")
    lines.append(f"🔎 En büyük pozisyon: <b>{r['top_symbol']}</b> (%{r['top_weight']:.0f})")
    lines.append(f"🧩 Çeşitlendirme skoru: <b>%{r['diversification']:.0f}</b> "
                 f"(%100 = tamamen dağınık, %0 = tek varlık)")
    lines.append(f"🌊 Portföy volatilitesi: <b>{r['risk_label']}</b> "
                 f"({r['avg_volatility']:.0f}% yıllık)" if r["avg_volatility"] else "🌊 Volatilite: veri yok")

    lines += ["", "<b>💡 Öneri:</b>"]
    if r["top_weight"] > 50:
        lines.append(f"⚠️ Portföyünün %{r['top_weight']:.0f}'i tek varlıkta. "
                     "Bunu %30'un altına çekmek riskini ciddi azaltır. /dengele")
    elif r["diversification"] < 50:
        lines.append("Çeşitlendirme düşük: farklı varlık sınıfları ekle (altın, endeks). /oner")
    else:
        lines.append("Çeşitlendirmen iyi durumda, planına devam et. 👌")

    if r["avg_volatility"] and r["avg_volatility"] > 50:
        lines.append("🔴 Volatilite yüksek: bu portföy sert dalgalanır, panik satışı yapma.")
    lines.append("⚠️ <i>Risk analizi yatırım tavsiyesi değildir.</i>")
    return "\n".join(lines)
