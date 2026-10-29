"""Grafik olusturucu (matplotlib) — Tema destekli (light/dark).

Fiyat + SMA20/50 + Bollinger bantlari ve alttaki RSI paneli tek PNG'de.
Sembol icin onbellekli veri kullanir, Telegram'a gonderilecek byte dondurur.
"""
import io

import matplotlib

matplotlib.use("Agg")  # GUI gerektirmez, dosyaya cizer
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from services import indicators as ind, market_data as md  # noqa: E402
from config import CHART_THEME


# Tema renk semalari
THEMES = {
    "light": {
        "bg": "#ffffff",
        "fg": "#24292f",
        "grid": "#d0d7de",
        "price": "#1f6feb",
        "sma20": "#d29922",
        "sma50": "#e5534b",
        "bb": "#8b949e",
        "bb_fill": "#8b949e",
        "rsi": "#a371f7",
        "rsi_overbought": "#e5534b",
        "rsi_oversold": "#2ea043",
        "rsi_fill": "#a371f7",
        "text": "#24292f",
    },
    "dark": {
        "bg": "#0d1117",
        "fg": "#e6edf3",
        "grid": "#30363d",
        "price": "#58a6ff",
        "sma20": "#d29922",
        "sma50": "#f85149",
        "bb": "#8b949e",
        "bb_fill": "#8b949e",
        "rsi": "#d2a8ff",
        "rsi_overbought": "#f85149",
        "rsi_oversold": "#3fb950",
        "rsi_fill": "#d2a8ff",
        "text": "#e6edf3",
    },
}


def _get_theme(name: str | None) -> dict:
    """Tema adına göre renk şeması döndürür."""
    if name is None:
        name = CHART_THEME
    return THEMES.get(name.lower(), THEMES["light"])


def build_chart(sym: str, period: str = "3mo", theme: str | None = None) -> bytes | None:
    """Fiyat + teknik gosterge grafigini PNG byte olarak dondurur.

    Args:
        sym: Sembol (örn: THYAO.IS, AAPL, BTC-USD)
        period: Zaman periyodu (1mo, 3mo, 6mo, 1y)
        theme: "light" veya "dark" (None ise config.CHART_THEME kullanılır)
    """
    df = md.get_history(sym, period=period)
    if df is None or df.empty or len(df) < 25:
        return None

    close = df["Close"]
    idx = df.index
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    bb_up, _, bb_lo = ind.bollinger(close)
    r = ind.rsi(close)

    t = _get_theme(theme)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor=t["bg"],
    )

    # Eksen renkleri
    for ax in (ax1, ax2):
        ax.set_facecolor(t["bg"])
        ax.tick_params(colors=t["fg"], labelcolor=t["fg"])
        for spine in ax.spines.values():
            spine.set_color(t["grid"])
        ax.xaxis.label.set_color(t["fg"])
        ax.yaxis.label.set_color(t["fg"])
        ax.title.set_color(t["fg"])

    # Ust panel: fiyat + gostergeler
    ax1.plot(idx, close, color=t["price"], lw=1.6, label="Fiyat")
    ax1.plot(idx, sma20, color=t["sma20"], lw=1.0, label="SMA20")
    ax1.plot(idx, sma50, color=t["sma50"], lw=1.0, label="SMA50")
    ax1.plot(idx, bb_up, color=t["bb"], lw=0.7, ls="--")
    ax1.plot(idx, bb_lo, color=t["bb"], lw=0.7, ls="--")
    ax1.fill_between(idx, bb_lo, bb_up, color=t["bb_fill"], alpha=0.07)
    ax1.set_title(f"{sym}  ({period})", fontsize=13, fontweight="bold", color=t["text"])
    legend = ax1.legend(loc="upper left", fontsize=8, ncol=4, facecolor=t["bg"], edgecolor=t["grid"])
    for text in legend.get_texts():
        text.set_color(t["fg"])
    ax1.grid(color=t["grid"], alpha=0.3)
    ax1.set_ylabel("Fiyat", color=t["fg"])

    # Alt panel: RSI
    ax2.plot(idx, r, color=t["rsi"], lw=1.2)
    ax2.axhline(70, color=t["rsi_overbought"], ls="--", lw=0.8)
    ax2.axhline(30, color=t["rsi_oversold"], ls="--", lw=0.8)
    ax2.fill_between(idx, 30, 70, color=t["rsi_fill"], alpha=0.06)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("RSI", fontsize=9, color=t["fg"])
    ax2.grid(color=t["grid"], alpha=0.3)

    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=t["bg"], edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()