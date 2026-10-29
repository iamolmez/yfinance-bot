"""Grafik olusturucu (matplotlib).

Fiyat + SMA20/50 + Bollinger bantlari ve alttaki RSI paneli tek PNG'de.
Sembol icin onbellekli veri kullanir, Telegram'a gonderilecek byte dondurur.
"""
import io

import matplotlib

matplotlib.use("Agg")  # GUI gerektirmez, dosyaya cizer
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from services import indicators as ind, market_data as md  # noqa: E402


def build_chart(sym: str, period: str = "3mo") -> bytes | None:
    """Fiyat + teknik gosterge grafigini PNG byte olarak dondurur."""
    df = md.get_history(sym, period=period)
    if df is None or df.empty or len(df) < 25:
        return None

    close = df["Close"]
    idx = df.index
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    bb_up, _, bb_lo = ind.bollinger(close)
    r = ind.rsi(close)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # Ust panel: fiyat + gostergeler
    ax1.plot(idx, close, color="#1f6feb", lw=1.6, label="Fiyat")
    ax1.plot(idx, sma20, color="#d29922", lw=1.0, label="SMA20")
    ax1.plot(idx, sma50, color="#e5534b", lw=1.0, label="SMA50")
    ax1.plot(idx, bb_up, color="#8b949e", lw=0.7, ls="--")
    ax1.plot(idx, bb_lo, color="#8b949e", lw=0.7, ls="--")
    ax1.fill_between(idx, bb_lo, bb_up, color="#8b949e", alpha=0.07)
    ax1.set_title(f"{sym}  ({period})", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left", fontsize=8, ncol=4)
    ax1.grid(alpha=0.25)
    ax1.set_ylabel("Fiyat")

    # Alt panel: RSI
    ax2.plot(idx, r, color="#a371f7", lw=1.2)
    ax2.axhline(70, color="#e5534b", ls="--", lw=0.8)
    ax2.axhline(30, color="#2ea043", ls="--", lw=0.8)
    ax2.fill_between(idx, 30, 70, alpha=0.06)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI", fontsize=9)
    ax2.grid(alpha=0.25)

    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
