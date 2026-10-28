"""Portföy korelasyon matrisi ve çeşitlendirme analizi.

Hisselerin birbirine ne kadar benziyor (korelasyon) — risk dağıtımı.
"""
import numpy as np
from collections import defaultdict

from database import get_transactions
from services import market_data as md, portfolio


def calculate_correlation_matrix(user_id: int, period: str = "1y") -> dict | None:
    """Portföydeki hisseler arası korelasyon matrisi."""
    pf = portfolio.get_portfolio(user_id)
    if not pf["positions"]:
        return None

    symbols = [p.symbol for p in pf["positions"]]
    if len(symbols) < 2:
        return {"error": "En az 2 hisse gerekli"}

    # Fiyat verilerini çek
    dfs = {}
    for sym in symbols:
        df = md.get_history(sym, period=period)
        if df is not None and not df.empty:
            dfs[sym] = df["Close"].pct_change().dropna()

    if len(dfs) < 2:
        return {"error": "Yeterli veri yok"}

    # Ortak tarihleri bul
    common_dates = set.intersection(*[set(df.index) for df in dfs.values()])
    if len(common_dates) < 30:
        return {"error": "Yeterli ortak veri yok (en az 30 gün)"}

    common_dates = sorted(common_dates)
    rets_matrix = np.array([dfs[s].loc[common_dates].values for s in symbols])

    # Korelasyon matrisi
    corr = np.corrcoef(rets_matrix)

    return {
        "symbols": list(symbols),
        "matrix": corr.tolist(),
        "period": period,
        "n_obs": len(common_dates),
    }


def diversification_metrics(user_id: int) -> dict:
    """Çeşitlendirme metrikleri: Herfindahl, etkili hisse sayısı, en yüksek korelasyon."""
    pf = portfolio.get_portfolio(user_id)
    if not pf["positions"]:
        return {"error": "Portföy boş"}

    total = sum(p.market_value for p in pf["positions"])
    weights = np.array([p.market_value / total for p in pf["positions"]])

    # Herfindahl-Hirschman Index
    hhi = np.sum(weights ** 2)
    effective_n = 1 / hhi if hhi > 0 else 1

    # Ağırlıklı ortalama korelasyon (varsa)
    corr_result = calculate_correlation_matrix(user_id)
    avg_corr = None
    max_corr_pair = None
    max_corr_val = -1

    if corr_result and "matrix" in corr_result:
        matrix = np.array(corr_result["matrix"])
        n = len(corr_result["symbols"])
        # Köşegen hariç üst üçgen
        mask = np.triu_indices(n, k=1)
        corrs = matrix[mask]
        avg_corr = float(np.mean(corrs))
        max_idx = np.argmax(corrs)
        max_corr_val = float(corrs[max_idx])
        max_corr_pair = (corr_result["symbols"][mask[0][max_idx]],
                         corr_result["symbols"][mask[1][max_idx]])

    return {
        "n_positions": len(pf["positions"]),
        "hhi": hhi,
        "effective_n": effective_n,
        "avg_correlation": avg_corr,
        "max_correlation": max_corr_val,
        "max_corr_pair": max_corr_pair,
        "concentration_risk": "Yüksek" if hhi > 0.25 else ("Orta" if hhi > 0.15 else "Düşük"),
    }


def correlation_text(corr_result: dict, div_metrics: dict) -> str:
    if "error" in corr_result:
        return f"❌ {corr_result['error']}"

    symbols = corr_result["symbols"]
    matrix = corr_result["matrix"]

    lines = [
        "📊 <b>Korelasyon Matrisi</b>",
        f"📅 Dönem: {corr_result['period']} ({corr_result['n_obs']} gözlem)",
        "",
        "<b>📊 Korelasyon Tablosu:</b>",
    ]

    # Tablo başlığı
    header = "       " + "  ".join(f"{s[:6]:>6}" for s in symbols)
    lines.append(f"<code>{header}</code>")

    for i, s in enumerate(symbols):
        row = f"{s[:6]:>6} " + "  ".join(f"{matrix[i][j]:>6.2f}" for j in range(len(symbols)))
        lines.append(f"<code>{row}</code>")

    lines.append("")
    lines.append("<b>📊 Çeşitlendirme Metrikleri:</b>")
    lines.append(f"• Pozisyon Sayısı: {div_metrics['n_positions']}")
    lines.append(f"• Herfindahl (HHI): <b>{div_metrics['hhi']:.3f}</b>")
    lines.append(f"• Etkili Hisse Sayısı: <b>{div_metrics['effective_n']:.1f}</b> (1 = tek hisse, N = tam dağıtık)")

    if div_metrics.get("avg_correlation") is not None:
        lines.append(f"• Ortalama Korelasyon: <b>{div_metrics['avg_correlation']:.2f}</b>")
        lines.append(f"• En Yüksek Korelasyon: <b>{div_metrics['max_correlation']:.2f}</b> ({div_metrics['max_corr_pair'][0]} - {div_metrics['max_corr_pair'][1]})")

    lines.append(f"• Konsantrasyon Riski: <b>{div_metrics['concentration_risk']}</b>")

    lines += [
        "",
        "📖 <b>Yorum:</b>",
        "   • HHI < 0.15: İyi dağıtık",
        "   • HHI 0.15-0.25: Orta konsantrasyon",
        "   • HHI > 0.25: Yüksek konsantrasyon (riskli)",
        "   • Ortalama korelasyon < 0.5: İyi çeşitlendirme",
        "   • En yüksek korelasyon > 0.8: Çift neredeyse aynı hareket ediyor",
        "",
        "⚠️ <i>Geçmiş korelasyon geleceği garanti etmez.</i>",
    ]

    return "\n".join(lines)