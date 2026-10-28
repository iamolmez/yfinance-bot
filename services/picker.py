"""Otomatik hisse secici.

Kullanici secim yapmaz; bot guvenli ve riskli havuzu teknik sinyallerle tarar,
profiline uygun karisimi tutarlarla birlikte onerir.

HIZ: Havuz taramasi (31 varlik) pahalidir; sonuclar 30 dk onbelleklenir.
/oner cagrisi onbellekten aninda doner, arka planda tazeleme yapilir.
"""
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from services import market_data as md, signals

# Her zaman taranacak aday havuzlari
SAFE_POOL = [
    "XU100.IS", "THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "ISCTR.IS",
    "TUPRS.IS", "FROTO.IS", "BIMAS.IS", "KCHOL.IS", "SAHOL.IS", "EREGL.IS",
    "AAPL", "MSFT", "JPM", "KO", "PG", "GC=F",
]
RISKY_POOL = [
    "SASA.IS", "HEKTS.IS", "ASTOR.IS", "ENKAI.IS",
    "TSLA", "AMD", "META", "NFLX", "NVDA",
    "BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD",
]

# Profil -> (guvenli yuzde, riskli yuzde)
_PROFILE_SPLIT = {
    "sakin": (80, 20),
    "dengeli": (60, 40),
    "atilgan": (40, 60),
}

# Sade dil aciklamalar (sinyale gore)
_SIMPLE = {
    "GÜÇLÜ AL": "teknik göstergeler oldukça olumlu",
    "AL": "teknik göstergeler olumlu",
    "HAFİF AL": "fiyatı makul, fırsat olabilir",
    "NÖTR": "ne pahalı ne ucuz",
    "HAFİF SAT": "biraz pahalanmış görünüyor",
    "SAT": "teknik göstergeler olumsuz",
    "GÜÇLÜ SAT": "teknik göstergeler oldukça olumsuz",
}

# ---- Havuz tarama onbellegi (31 varlik taramasi pahali) ----
_SCORE_CACHE: dict[str, dict] = {}
_SCORE_TS: float = 0.0
_SCORE_TTL = 30 * 60  # 30 dakika
_scan_lock = threading.Lock()


def _score_one(sym: str):
    try:
        return signals.score_symbol(sym)
    except Exception:
        return None


def refresh_scores(force: bool = False) -> None:
    """Havuzdaki tum sembolleri tarar ve onbellege yazar (bloklayici)."""
    global _SCORE_TS
    now = time.time()
    if not force and now - _SCORE_TS < _SCORE_TTL:
        return
    with _scan_lock:
        if not force and now - _SCORE_TS < _SCORE_TTL:
            return
        pool = list(dict.fromkeys(SAFE_POOL + RISKY_POOL))
        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(_score_one, pool))
        for sym, sig in zip(pool, results):
            if sig:
                _SCORE_CACHE[sym] = sig
        _SCORE_TS = time.time()


def refresh_in_background(force: bool = False) -> None:
    """Taramayi arka planda yapar; cagri aninda doner."""
    threading.Thread(target=refresh_scores, args=(force,), daemon=True).start()


def scores_fresh() -> bool:
    """Onbellekte taze veri var mi?"""
    return bool(_SCORE_CACHE) and (time.time() - _SCORE_TS < _SCORE_TTL)


def scores_ready() -> bool:
    """En az bir kez tarama yapildi mi (ilk kullanim bloklayici olur)."""
    return bool(_SCORE_CACHE)


def _scan(pool: list[str]) -> dict[str, dict]:
    """Havuz skorlarini onbellekten okur."""
    return {s: _SCORE_CACHE[s] for s in pool if s in _SCORE_CACHE}


def _amounts(scores: list[dict], budget: float) -> dict[str, float]:
    """Skor agirlikli tutar dagilimi yapar."""
    total_score = sum(max(s["score"], 1) for s in scores)
    if total_score <= 0 or budget <= 0:
        return {s["symbol"]: 0.0 for s in scores}
    return {
        s["symbol"]: round(budget * max(s["score"], 1) / total_score, 2)
        for s in scores
    }


def pick(plan: dict, portfolio_positions: list, cash: float = 0.0) -> dict:
    """Plan + portfoye gore otomatik alim/satim onerileri uretir.

    Donus:
      {"invest_share", "safe_pct", "risky_pct",
       "safe": [ {symbol, score, signal, amount, reason, held} ],
       "risky": [ ... ],
       "sells": [ {symbol, score, signal, amount} ]}
    """
    if not scores_ready():
        refresh_scores(force=True)  # ilk kullanimda bloklar (bir kez)
    else:
        refresh_scores()  # TTL gectiyse yeniler, degilse aninda doner

    risk = plan.get("risk", "dengeli")
    safe_pct, risky_pct = _PROFILE_SPLIT.get(risk, (60, 40))
    invest_share = plan.get("invest_share", 0.0)
    safe_budget = invest_share * safe_pct / 100
    risky_budget = invest_share * risky_pct / 100

    # Mevcut portfoy degerleri (sembol -> market value)
    held = {p.symbol: p.market_value for p in portfolio_positions}

    safe_scores = [
        s for s in _scan(SAFE_POOL).values()
        if s["score"] >= 2 and not (held.get(s["symbol"], 0) >= safe_budget)
    ]
    risky_scores = [
        s for s in _scan(RISKY_POOL).values()
        if s["score"] >= 1 and not (held.get(s["symbol"], 0) >= risky_budget)
    ]
    safe_scores.sort(key=lambda s: s["score"], reverse=True)
    risky_scores.sort(key=lambda s: s["score"], reverse=True)
    safe_scores = safe_scores[:2]
    risky_scores = risky_scores[:2]

    safe_amts = _amounts(safe_scores, safe_budget)
    risky_amts = _amounts(risky_scores, risky_budget)

    safe = [
        {"symbol": s["symbol"], "score": s["score"], "signal": s["signal"],
         "amount": safe_amts.get(s["symbol"], 0.0),
         "reason": _SIMPLE.get(s["signal"], ""),
         "held": held.get(s["symbol"], 0.0)}
        for s in safe_scores
    ]
    risky = [
        {"symbol": s["symbol"], "score": s["score"], "signal": s["signal"],
         "amount": risky_amts.get(s["symbol"], 0.0),
         "reason": _SIMPLE.get(s["signal"], ""),
         "held": held.get(s["symbol"], 0.0)}
        for s in risky_scores
    ]

    # Portfoydeki sat sinyalleri
    sells = []
    for sym, mv in held.items():
        try:
            sig = signals.score_symbol(sym)
        except Exception:
            continue
        if sig and sig["score"] <= -3:
            sells.append({"symbol": sym, "score": sig["score"],
                          "signal": sig["signal"], "amount": mv})

    # Nakde gore olcek: onerilen alimlar eldeki nakdi asmasin
    total_suggested = sum(x["amount"] for x in safe + risky)
    if total_suggested > cash and total_suggested > 0:
        ratio = cash / total_suggested
        for x in safe + risky:
            x["amount"] = round(x["amount"] * ratio, 2)

    return {
        "invest_share": invest_share,
        "safe_pct": safe_pct,
        "risky_pct": risky_pct,
        "safe": safe,
        "risky": risky,
        "sells": sells,
        "cash": cash,
    }


def pick_message(result: dict) -> str:
    lines = ["🎯 <b>Otomatik Seçimler</b>"]
    if result["invest_share"] <= 0:
        lines += [
            "",
            "Planında yatırım payı tanımlı değil. Önce /basla ile plan kur.",
        ]
        return "\n".join(lines)

    lines.append(f"📅 Aylık yatırım payın: <b>{result['invest_share']:,.2f} ₺</b>")
    lines.append(
        f"🧩 Dağılım: 🛡️ güvenli %{result['safe_pct']} | ⚡ riskli %{result['risky_pct']}"
    )
    if result["cash"] > 0:
        lines.append(f"💵 Eldeki nakit: {result['cash']:,.2f} ₺")

    if result["safe"]:
        lines += ["", f"🛡️ <b>Güvenli öneriler</b> (%{result['safe_pct']}):"]
        for x in result["safe"]:
            held_txt = f"\n   📌 Zaten {x['held']:,.0f} ₺ var" if x["held"] else ""
            lines.append(
                f"• <b>{x['symbol']}</b> — {x['signal']} (skor {x['score']:+d})\n"
                f"  💰 Önerilen: <b>{x['amount']:,.0f} ₺</b> — {x['reason']}{held_txt}"
            )
    else:
        lines += ["", "🛡️ Güvenli tarafta bugün fırsat yok. Nakitte beklemek de bir karardır."]

    if result["risky"]:
        lines += ["", f"⚡ <b>Riskli öneriler</b> (%{result['risky_pct']}):"]
        for x in result["risky"]:
            held_txt = f"\n   📌 Zaten {x['held']:,.0f} ₺ var" if x["held"] else ""
            lines.append(
                f"• <b>{x['symbol']}</b> — {x['signal']} (skor {x['score']:+d})\n"
                f"  💰 Önerilen: <b>{x['amount']:,.0f} ₺</b> — {x['reason']}{held_txt}"
            )
    else:
        lines += ["", "⚡ Riskli tarafta bugün fırsat yok, zorlama."]

    if result["sells"]:
        lines += ["", "🛑 <b>Satmayı düşünebilirsin:</b>"]
        for x in result["sells"][:3]:
            lines.append(
                f"• {x['symbol']} — {x['signal']} (skor {x['score']:+d}), "
                f"değeri {x['amount']:,.0f} ₺"
            )

    lines += [
        "",
        "💡 Alımı kaydet: /ekle SYMBOL ADET FIYAT",
        "⚠️ <i>Teknik analize dayalıdır, yatırım tavsiyesi değildir.</i>",
    ]
    return "\n".join(lines)
