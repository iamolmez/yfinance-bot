"""Strateji geriye donuk testi (backtest).

Sinyal motorunun kuralini gecmis veri uzerinde calistirir: AL sinyali gelince
al, SAT sinyali gelince sat. Sonucu 'hic islem yapmadan tutmak' ile karsilastirir.

BILGI: Gecmis performans gelecegi garanti etmez; sadece stratejinin ne kadar
disiplinli calistigini gosterir.
"""
import numpy as np

from services import indicators as ind, market_data as md, signals


def backtest(sym: str, period: str = "2y", initial: float = 10000,
             buy_score: int = 3, sell_score: int = -3) -> dict | None:
    """Tek sembol icin strateji backtesti."""
    df = md.get_history(sym, period=period)
    if df is None or df.empty or len(df) < 70:
        return None

    close = df["Close"]
    r = ind.rsi(close)
    _macd_line, _sig_line, hist = ind.macd(close)
    sma20 = ind.sma(close, 20)
    sma50 = ind.sma(close, 50)
    bb_up, _bb_mid, bb_lo = ind.bollinger(close)

    prices = close.values
    n = len(prices)
    cash = float(initial)
    shares = 0.0
    entry_price = 0.0
    n_wins = 0
    n_losses = 0
    n_sells = 0
    max_equity = float(initial)
    max_dd = 0.0

    for i in range(50, n):
        price = float(prices[i])
        a = {
            "price": price,
            "rsi": float(r.iloc[i]),
            "macd_hist": float(hist.iloc[i]),
            "macd_hist_prev": float(hist.iloc[i - 1]),
            "sma20": float(sma20.iloc[i]),
            "sma50": float(sma50.iloc[i]),
            "bb_lower": float(bb_lo.iloc[i]),
            "bb_upper": float(bb_up.iloc[i]),
            "vol_ratio": None,
        }
        score = signals.score_from_analysis(a)

        if shares == 0 and score >= buy_score:
            shares = cash / price
            cash = 0.0
            entry_price = price
        elif shares > 0 and score <= sell_score:
            proceeds = shares * price
            if proceeds >= entry_price * shares:
                n_wins += 1
            else:
                n_losses += 1
            cash = proceeds
            shares = 0.0
            n_sells += 1

        equity = cash + shares * price
        max_equity = max(max_equity, equity)
        dd = (max_equity - equity) / max_equity if max_equity else 0.0
        max_dd = max(max_dd, dd)

    final_value = cash + shares * float(prices[-1])
    strat_return = (final_value / initial - 1) * 100
    buyhold_return = (float(prices[-1]) / float(prices[0]) - 1) * 100

    return {
        "symbol": sym,
        "period": period,
        "initial": initial,
        "final": final_value,
        "strategy_return": strat_return,
        "buyhold_return": buyhold_return,
        "n_trades": n_sells,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "max_drawdown": max_dd * 100,
    }


def backtest_text(r: dict) -> str:
    if not r:
        return "Yetersiz veri (en az 70 gün geçmiş gerekir)."
    verdict = ""
    diff = r["strategy_return"] - r["buyhold_return"]
    if r["n_trades"] == 0:
        verdict = "Bu dönemde alım sinyali hiç gelmedi, para nakitte kaldı."
    elif diff > 5:
        verdict = "Strateji, pasif tutmayı <b>GEÇTİ</b> ✅"
    elif diff < -5:
        verdict = "Strateji, pasif tutmanın <b>gerisinde</b> kaldı ⚠️"
    else:
        verdict = "Strateji, pasif tutmayla <b>başabaş</b>."

    lines = [
        f"📊 <b>Backtest: {r['symbol']}</b> ({r['period']})",
        f"💰 Başlangıç: {r['initial']:,.0f} ₺ → Bitiş: <b>{r['final']:,.0f} ₺</b>",
        "",
        f"📈 Strateji getirisi: <b>%{r['strategy_return']:+.1f}</b>",
        f"📉 Pasif tutma (al-sat yok): %{r['buyhold_return']:+.1f}",
        f"🧾 İşlem: {r['n_trades']} tam tur ({r['n_wins']} kazanç / {r['n_losses']} kayıp)",
        f"📉 Maks düşüş: %-{r['max_drawdown']:.1f}",
        "",
        f"💬 {verdict}",
        "",
        "⚠️ <i>Geçmiş test geleceği garanti etmez; sadece kural disiplinini ölçer.</i>",
    ]
    return "\n".join(lines)
