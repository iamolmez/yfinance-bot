"""Risk metrikleri: Sharpe, Sortino, Calmar, Max Drawdown, Monte Carlo simülasyonu.

Profesyonel portföy risk analizi.
"""
import numpy as np
from datetime import date, timedelta

from database import get_portfolio_snapshots


def calculate_metrics(user_id: int, days: int = 365, risk_free_rate: float = 0.15) -> dict:
    """Portföy risk metriklerini hesaplar.

    Args:
        user_id: Kullanıcı ID
        days: Geriye dönük gün sayısı
        risk_free_rate: Yıllık risksiz getiri (TL için ~%15, USD için ~%5)

    Returns:
        Dict: Sharpe, Sortino, Calmar, Max DD, Volatilite, VaR, CVaR
    """
    snaps = get_portfolio_snapshots(user_id, days)
    if len(snaps) < 30:
        return {"error": "Yetersiz veri (en az 30 gün snapshot gerekli)"}

    values = np.array([s["total_value"] for s in snaps])
    returns = np.diff(values) / values[:-1]

    if len(returns) < 2:
        return {"error": "Yetersiz getiri verisi"}

    # Temel metrikler
    daily_rf = (1 + risk_free_rate) ** (1/252) - 1
    excess = returns - daily_rf

    # Volatilite (yıllık)
    vol_daily = np.std(returns, ddof=1)
    vol_annual = vol_daily * np.sqrt(252)

    # Sharpe
    sharpe = np.mean(excess) / vol_daily * np.sqrt(252) if vol_daily > 0 else 0

    # Sortino (sadece negatif getiriler)
    downside = returns[returns < daily_rf]
    downside_vol = np.std(downside, ddof=1) if len(downside) > 1 else vol_daily
    sortino = np.mean(excess) / downside_vol * np.sqrt(252) if downside_vol > 0 else 0

    # Max Drawdown
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_dd = np.min(drawdown)

    # Calmar
    ann_return = np.prod(1 + returns) ** (252 / len(returns)) - 1
    calmar = ann_return / abs(max_dd) if max_dd < 0 else 0

    # VaR (Value at Risk) %95, %99
    var_95 = np.percentile(returns, 5)
    var_99 = np.percentile(returns, 1)

    # CVaR (Conditional VaR / Expected Shortfall)
    cvar_95 = np.mean(returns[returns <= var_95]) if np.any(returns <= var_95) else var_95
    cvar_99 = np.mean(returns[returns <= var_99]) if np.any(returns <= var_99) else var_99

    # Yıllık getiri
    total_return = np.prod(1 + returns) - 1
    ann_return = (1 + total_return) ** (252 / len(returns)) - 1

    return {
        "period_days": len(returns),
        "annual_return": ann_return * 100,
        "volatility": vol_annual * 100,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_dd * 100,
        "var_95": var_95 * 100,
        "var_99": var_99 * 100,
        "cvar_95": cvar_95 * 100,
        "cvar_99": cvar_99 * 100,
    }


def monte_carlo_simulation(user_id: int, years: int = 10, n_sim: int = 200,
                           initial: float | None = None) -> dict:
    """Monte Carlo simülasyonu: portföyün gelecekte olası yolları.

    Args:
        user_id: Kullanıcı ID
        years: Simülasyon yıl sayısı
        n_sim: Simülasyon sayısı
        initial: Başlangıç değeri (None ise mevcut portföy değeri)

    Returns:
        Dict: percentiles, final_values, paths
    """
    snaps = get_portfolio_snapshots(user_id, 365)
    if len(snaps) < 60:
        return {"error": "Yetersiz veri (en az 60 gün snapshot gerekli)"}

    values = np.array([s["total_value"] for s in snaps])
    returns = np.diff(values) / values[:-1]

    mu = np.mean(returns)
    sigma = np.std(returns, ddof=1)

    if initial is None:
        initial = float(values[-1])

    n_days = years * 252
    dt = 1 / 252

    paths = np.zeros((n_sim, n_days + 1))
    paths[:, 0] = initial

    for i in range(n_days):
        z = np.random.normal(0, 1, n_sim)
        paths[:, i + 1] = paths[:, i] * np.exp(
            (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
        )

    final_values = paths[:, -1]

    return {
        "initial": initial,
        "years": years,
        "n_sim": n_sim,
        "mean_final": np.mean(final_values),
        "median_final": np.median(final_values),
        "p5": np.percentile(final_values, 5),
        "p10": np.percentile(final_values, 10),
        "p25": np.percentile(final_values, 25),
        "p50": np.percentile(final_values, 50),
        "p75": np.percentile(final_values, 75),
        "p90": np.percentile(final_values, 90),
        "p95": np.percentile(final_values, 95),
        "prob_loss": np.mean(final_values < initial) * 100,
        "prob_double": np.mean(final_values >= 2 * initial) * 100,
        "paths_sample": paths[:min(10, n_sim), ::max(1, n_days // 30)].tolist(),
    }


def monte_carlo_text(result: dict) -> str:
    if "error" in result:
        return f"❌ {result['error']}"

    lines = [
        f"🎲 <b>Monte Carlo Simülasyonu</b> ({result['years']} yıl, {result['n_sim']} senaryo)",
        f"💰 Başlangıç: {result['initial']:,.0f} ₺",
        "",
        "📊 <b>Olasılık Dağılımı (Yıl Sonu Değerleri):</b>",
        f"   P5 (Kötü): {result['p5']:,.0f} ₺",
        f"   P10: {result['p10']:,.0f} ₺",
        f"   P25: {result['p25']:,.0f} ₺",
        f"   P50 (Medyan): <b>{result['p50']:,.0f} ₺</b>",
        f"   P75: {result['p75']:,.0f} ₺",
        f"   P90: {result['p90']:,.0f} ₺",
        f"   P95 (İyi): {result['p95']:,.0f} ₺",
        "",
        f"📉 Kayıp Olasılığı: <b>%{result['prob_loss']:.1f}</b> (değer < başlangıç)",
        f"📈 İkileşme Olasılığı: <b>%{result['prob_double']:.1f}</b> (değer ≥ 2x başlangıç)",
        f"📈 Ortalama Beklenen: {result['mean_final']:,.0f} ₺",
        "",
        "⚠️ <i>Simülasyon geçmiş volatiliteye dayanır; gerçeği garanti etmez.</i>",
    ]
    return "\n".join(lines)


def metrics_text(metrics: dict) -> str:
    if "error" in metrics:
        return f"❌ {metrics['error']}"

    lines = [
        "📉 <b>Risk Metrikleri</b>",
        f"📅 Dönem: {metrics['period_days']} gün",
        "",
        f"📈 Yıllık Getiri: <b>%{metrics['annual_return']:.2f}</b>",
        f"📊 Volatilite (Yıllık): <b>%{metrics['volatility']:.2f}</b>",
        f"⚡ Sharpe Ratio: <b>{metrics['sharpe']:.2f}</b>",
        f"📉 Sortino Ratio: <b>{metrics['sortino']:.2f}</b>",
        f"📉 Calmar Ratio: <b>{metrics['calmar']:.2f}</b>",
        f"📉 Max Drawdown: <b>%{metrics['max_drawdown']:.2f}</b>",
        "",
        f"📉 VaR %95 (Günlük): %{metrics['var_95']:.2f}",
        f"📉 VaR %99 (Günlük): %{metrics['var_99']:.2f}",
        f"📉 CVaR %95: %{metrics['cvar_95']:.2f}",
        f"📉 CVaR %99: %{metrics['cvar_99']:.2f}",
        "",
        "📖 <b>Yorum:</b>",
        "   • Sharpe > 1: İyi risk-getiri dengesi",
        "   • Sortino > 1: Aşağı riskine göre iyi getiri",
        "   • Calmar > 1: Drawdown'a göre iyi getiri",
        "   • Max DD < %20: Kabul edilebilir risk",
        "",
        "⚠️ <i>Geçmiş veriye dayanır; gerçeği garanti etmez.</i>",
    ]
    return "\n".join(lines)