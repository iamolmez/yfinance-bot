"""Benchmark karşılaştırması: Portföy vs XU100 / S&P 500 / Özel endeks.

Portföy getirisi vs endeks getirisi, alfa, beta, tracking error.
"""
import numpy as np

from database import get_portfolio_snapshots
from services import market_data as md, portfolio


def get_benchmark_history(symbol: str, days: int = 365) -> list[float]:
    """Endeks/benchmark geçmiş getirilerini çeker (günlük kapanış)."""
    df = md.get_history(sym, period=f"{days}d")
    if df is None or df.empty:
        return []
    closes = df["Close"].dropna().values
    returns = np.diff(closes) / closes[:-1]
    return returns.tolist()


def calculate_portfolio_returns(user_id: int, days: int = 365) -> list[float]:
    """Portföy günlük getirilerini hesaplar (snapshot'tan)."""
    snaps = get_portfolio_snapshots(user_id, days)
    if len(snaps) < 2:
        return []
    values = [s["total_value"] for s in snaps]
    returns = np.diff(values) / np.array(values[:-1])
    return returns.tolist()


def compare_to_benchmark(user_id: int, benchmark: str = "XU100.IS",
                         days: int = 365) -> dict:
    """Portföyü benchmark ile karşılaştırır."""
    pf_returns = calculate_portfolio_returns(user_id, days)
    if len(pf_returns) < 30:
        return {"error": "Yetersiz veri (en az 30 gün snapshot gerekli)"}

    # Benchmark'i çöz
    if benchmark.upper() in ("XU100", "BIST100", "XU100"):
        bench_sym = "XU100.IS"
    elif benchmark.upper() in ("SP500", "S&P500", "SPX"):
        bench_sym = "^GSPC"
    else:
        bench_sym = benchmark

    bench_returns = get_benchmark_history(bench_sym, days)
    if len(bench_returns) < len(pf_returns):
        return {"error": "Benchmark verisi yetersiz"}

    # Aynı uzunlukta kes
    n = min(len(pf_returns), len(bench_returns))
    pf_r = np.array(pf_returns[-n:])
    bm_r = np.array(bench_returns[-n:])

    # Metrikler
    pf_cum = np.prod(1 + pf_r) - 1
    bm_cum = np.prod(1 + bm_r) - 1
    alpha = pf_cum - bm_cum

    # Beta
    cov = np.cov(pf_r, bm_r)[0, 1]
    var_bm = np.var(bm_r)
    beta = cov / var_bm if var_bm > 0 else 1.0

    # Tracking Error
    te = np.std(pf_r - bm_r) * np.sqrt(252)

    # Information Ratio
    ir = alpha / te if te > 0 else 0

    # Up/Down Capture
    up_mask = bm_r > 0
    down_mask = bm_r < 0
    up_capture = np.mean(pf_r[up_mask]) / np.mean(bm_r[up_mask]) if np.any(up_mask) and np.mean(bm_r[up_mask]) != 0 else 1
    down_capture = np.mean(pf_r[down_mask]) / np.mean(bm_r[down_mask]) if np.any(down_mask) and np.mean(bm_r[down_mask]) != 0 else 1

    return {
        "benchmark": bench_sym,
        "period_days": n,
        "portfolio_return": pf_cum * 100,
        "benchmark_return": bm_cum * 100,
        "alpha": alpha * 100,
        "beta": beta,
        "tracking_error": te * 100,
        "information_ratio": ir,
        "up_capture": up_capture,
        "down_capture": down_capture,
    }


def benchmark_text(result: dict) -> str:
    if "error" in result:
        return f"❌ {result['error']}"

    lines = [
        "📊 <b>Benchmark Karşılaştırması</b>",
        f"📈 Endeks: {result['benchmark']}",
        f"📅 Dönem: {result['period_days']} gün",
        "",
        f"📈 Portföy Getirisi: <b>%{result['portfolio_return']:.2f}</b>",
        f"📉 Endeks Getirisi: <b>%{result['benchmark_return']:.2f}</b>",
        f"⚡ Alfa: <b>%{result['alpha']:+.2f}</b> (endeks üstünde/altında)",
        f"📊 Beta: <b>{result['beta']:.2f}</b> (piyasa hassasiyeti)",
        f"🎯 Tracking Error: %{result['tracking_error']:.2f}",
        f"📊 Information Ratio: {result['information_ratio']:.2f}",
        "",
        f"📈 Up Capture: %{result['up_capture']*100:.0f} (yükselişte endeksin ne kadarı alındı)",
        f"📉 Down Capture: %{result['down_capture']*100:.0f} (düşüşte endeksin ne kadarı hissedildi)",
        "",
        "⚠️ <i>Geçmiş performans geleceği garanti etmez.</i>"
    ]
    return "\n".join(lines)