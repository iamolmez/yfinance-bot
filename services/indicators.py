"""Teknik gosterge hesaplamalari (pandas/numpy tabanli)."""
import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    r = 100 - (100 / (1 + rs))
    return r.fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """(macd, signal, histogram) dondurur."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = sma(series, period)
    std = series.rolling(period).std(ddof=0)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    return upper, mid, lower


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Gercek Aralik (volatilite olcusu)."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def volume_ratio(df: pd.DataFrame, period: int = 20) -> float | None:
    """Son hacim / ortalamaya oran."""
    if "Volume" not in df or len(df) < 2:
        return None
    vol = df["Volume"].dropna()
    if len(vol) < 2 or vol.iloc[-1] == 0:
        return None
    avg = vol.iloc[-period:].mean()
    if not avg:
        return None
    return float(vol.iloc[-1] / avg)


def full_analysis(df: pd.DataFrame) -> dict:
    """Gerekli tum gostergelerin son degerlerini dondurur."""
    close = df["Close"]
    price = float(close.iloc[-1])

    r = rsi(close)
    macd_line, signal_line, hist = macd(close)
    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    bb_upper, bb_mid, bb_lower = bollinger(close)
    a = atr(df)

    last_90 = close.tail(90)
    support = float(last_90.min()) if len(last_90) else price
    resistance = float(last_90.max()) if len(last_90) else price

    rsi_val = float(r.iloc[-1]) if len(r) and not np.isnan(r.iloc[-1]) else 50.0
    hist_val = float(hist.iloc[-1]) if len(hist) and not np.isnan(hist.iloc[-1]) else 0.0
    hist_prev = float(hist.iloc[-2]) if len(hist) > 1 and not np.isnan(hist.iloc[-2]) else 0.0
    macd_val = float(macd_line.iloc[-1]) if len(macd_line) and not np.isnan(macd_line.iloc[-1]) else 0.0
    macd_sig = float(signal_line.iloc[-1]) if len(signal_line) and not np.isnan(signal_line.iloc[-1]) else 0.0
    s20 = float(sma20.iloc[-1]) if len(sma20) and not np.isnan(sma20.iloc[-1]) else price
    s50 = float(sma50.iloc[-1]) if len(sma50) and not np.isnan(sma50.iloc[-1]) else price
    bb_lo = float(bb_lower.iloc[-1]) if len(bb_lower) and not np.isnan(bb_lower.iloc[-1]) else price
    bb_up = float(bb_upper.iloc[-1]) if len(bb_upper) and not np.isnan(bb_upper.iloc[-1]) else price
    atr_val = float(a.iloc[-1]) if len(a) and not np.isnan(a.iloc[-1]) else price * 0.02
    vol_ratio = volume_ratio(df)

    return {
        "price": price,
        "rsi": rsi_val,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "macd_hist": hist_val,
        "macd_hist_prev": hist_prev,
        "sma20": s20,
        "sma50": s50,
        "bb_upper": bb_up,
        "bb_lower": bb_lo,
        "atr": atr_val,
        "support": support,
        "resistance": resistance,
        "vol_ratio": vol_ratio,
    }


def rsi_label(v: float) -> str:
    if v <= 30:
        return "Aşırı satım"
    if v < 40:
        return "Zayıf (alım bölgesi)"
    if v <= 60:
        return "Nötr"
    if v <= 70:
        return "Güçlü (satım bölgesi)"
    return "Aşırı alım"


def trend_label(price: float, sma20: float, sma50: float) -> str:
    if price > sma20 > sma50:
        return "Yükseliş trendi"
    if price < sma20 < sma50:
        return "Düşüş trendi"
    if price > sma20:
        return "Kısa vade güçlü"
    return "Kısa vade zayıf"
