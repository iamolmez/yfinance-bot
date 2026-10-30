"""Broker komisyon modelleri ve karşılaştırma.

Desteklenen brokerlar:
- Midast: $1.50/lot (US), ₺2.50/lot (BIST) + %0.1 spread
- IsYatirim: $2.00/lot (US), ₺3.00/lot (BIST)
- GarantiYatirim: $1.90/lot (US), ₺2.90/lot (BIST)
- VakifYatirim: $1.80/lot (US), ₺2.70/lot (BIST)
- DenizYatirim: $2.00/lot (US), ₺3.00/lot (BIST)
- Komisyonsuz (BIST): ₺0 + %0.1 spread (sadece spread maliyeti)
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Market(Enum):
    BIST = "bist"
    US = "us"
    CRYPTO = "crypto"


@dataclass
class BrokerCommission:
    """Broker komisyon modeli."""
    name: str
    # Sabit komisyon (lot başına)
    fixed_per_lot_us: float = 0.0      # $/lot (US hisse)
    fixed_per_lot_bist: float = 0.0    # ₺/lot (BIST)
    fixed_per_lot_crypto: float = 0.0  # $/lot (Kripto)
    
    # Yüzdesel komisyon (işlem tutarının %)
    pct_us: float = 0.0
    pct_bist: float = 0.0
    pct_crypto: float = 0.0
    
    # Minimum komisyon
    min_us: float = 0.0
    min_bist: float = 0.0
    min_crypto: float = 0.0
    
    # Spread maliyeti (yüzde)
    spread_pct: float = 0.0
    
    # Aylık/ yıllık hesap ücreti
    monthly_fee: float = 0.0
    currency: str = "TRY"  # hesap ücreti para birimi


# Tanımlı brokerlar
BROKERS = {
    "midas": BrokerCommission(
        name="MİDAS",
        fixed_per_lot_us=1.50,
        fixed_per_lot_bist=2.50,
        fixed_per_lot_crypto=0.0,
        pct_us=0.0005,      # %0.05
        pct_bist=0.0005,
        pct_crypto=0.001,
        min_us=1.50,
        min_bist=2.50,
        min_crypto=1.00,
        spread_pct=0.0008,  # %0.08
        monthly_fee=0,
        currency="TRY",
    ),
    "isyatirim": BrokerCommission(
        name="İŞ YATIRIM",
        fixed_per_lot_us=2.00,
        fixed_per_lot_bist=3.00,
        fixed_per_lot_crypto=0.0,
        pct_us=0.001,
        pct_bist=0.001,
        pct_crypto=0.0015,
        min_us=2.00,
        min_bist=3.00,
        min_crypto=2.00,
        spread_pct=0.001,
        monthly_fee=0,
        currency="TRY",
    ),
    "garanti": BrokerCommission(
        name="GARANTİ YATIRIM",
        fixed_per_lot_us=1.90,
        fixed_per_lot_bist=2.90,
        fixed_per_lot_crypto=0.0,
        pct_us=0.0008,
        pct_bist=0.0008,
        pct_crypto=0.0012,
        min_us=1.90,
        min_bist=2.90,
        min_crypto=1.50,
        spread_pct=0.0009,
        monthly_fee=0,
        currency="TRY",
    ),
    "vakif": BrokerCommission(
        name="VAKIF YATIRIM",
        fixed_per_lot_us=1.80,
        fixed_per_lot_bist=2.70,
        fixed_per_lot_crypto=0.0,
        pct_us=0.0007,
        pct_bist=0.0007,
        pct_crypto=0.001,
        min_us=1.80,
        min_bist=2.70,
        min_crypto=1.00,
        spread_pct=0.0008,
        monthly_fee=0,
        currency="TRY",
    ),
    "deniz": BrokerCommission(
        name="DENİZ YATIRIM",
        fixed_per_lot_us=2.00,
        fixed_per_lot_bist=3.00,
        fixed_per_lot_crypto=0.0,
        pct_us=0.001,
        pct_bist=0.001,
        pct_crypto=0.0015,
        min_us=2.00,
        min_bist=3.00,
        min_crypto=2.00,
        spread_pct=0.001,
        monthly_fee=0,
        currency="TRY",
    ),
    "komisyonsuz_bist": BrokerCommission(
        name="KOMİSYONSUZ (Sadece Spread)",
        fixed_per_lot_us=0.0,
        fixed_per_lot_bist=0.0,
        fixed_per_lot_crypto=0.0,
        pct_us=0.0,
        pct_bist=0.0,
        pct_crypto=0.0,
        min_us=0.0,
        min_bist=0.0,
        min_crypto=0.0,
        spread_pct=0.0015,  # %0.15 spread
        monthly_fee=0,
        currency="TRY",
    ),
    "interactive_brokers": BrokerCommission(
        name="Interactive Brokers (IBKR)",
        fixed_per_lot_us=0.35,      # $0.35/lot (min $0.35, max %1)
        fixed_per_lot_bist=0.0,
        fixed_per_lot_crypto=0.0,
        pct_us=0.0005,
        pct_bist=0.0,
        pct_crypto=0.001,
        min_us=0.35,
        min_bist=0.0,
        min_crypto=0.50,
        spread_pct=0.0003,
        monthly_fee=0,  # $10/min ay (harcama <$100k ise)
        currency="USD",
    ),
}


def calculate_commission(broker_key: str, market: Market, qty: float, price: float, fx_rate: float = 1.0) -> float:
    """İşlem için toplam komisyon hesaplar."""
    broker = BROKERS.get(broker_key.lower())
    if not broker:
        return 0.0
    
    if market == Market.US:
        fixed = broker.fixed_per_lot_us * qty
        pct = qty * price * broker.pct_us
        min_comm = broker.min_us
        spread = qty * price * broker.spread_pct
        total_usd = max(fixed + pct, min_comm) + spread
        return total_usd * fx_rate
    
    elif market == Market.BIST:
        fixed = broker.fixed_per_lot_bist * qty
        pct = qty * price * broker.pct_bist
        min_comm = broker.min_bist
        spread = qty * price * broker.spread_pct
        return max(fixed + pct, min_comm) + spread
    
    elif market == Market.CRYPTO:
        fixed = broker.fixed_per_lot_crypto * qty
        pct = qty * price * broker.pct_crypto
        min_comm = broker.min_crypto
        spread = qty * price * broker.spread_pct
        total_usd = max(fixed + pct, min_comm) + spread
        return total_usd * fx_rate
    
    return 0.0


def calculate_total_cost(broker_key: str, market: Market, qty: float, price: float, fx_rate: float = 1.0) -> dict:
    """Toplam maliyet detayı."""
    broker = BROKERS.get(broker_key.lower())
    if not broker:
        return {"error": "Broker bulunamadı"}
    
    commission = calculate_commission(broker_key, market, qty, price, fx_rate)
    gross = qty * price * (fx_rate if market in (Market.US, Market.CRYPTO) else 1.0)
    
    return {
        "broker": broker.name,
        "gross_value": gross,
        "commission": commission,
        "net_cost": gross + commission,
        "commission_pct": (commission / gross * 100) if gross > 0 else 0,
        "monthly_fee": broker.monthly_fee * (fx_rate if broker.currency == "USD" else 1.0),
    }


def compare_brokers(market: Market, qty: float, price: float, fx_rate: float = 1.0, 
                    selected_brokers: list[str] = None) -> list[dict]:
    """Brokerları maliyet bazında karşılaştır."""
    if selected_brokers is None:
        selected_brokers = list(BROKERS.keys())
    
    results = []
    for key in selected_brokers:
        if key in BROKERS:
            cost = calculate_total_cost(key, market, qty, price, fx_rate)
            if "error" not in cost:
                results.append(cost)
    
    # Net maliyete göre sırala (en ucuz ilk)
    results.sort(key=lambda x: x["net_cost"])
    
    # Rank ekle
    for i, r in enumerate(results):
        r["rank"] = i + 1
    
    return results


def format_comparison(comparison: list[dict], symbol: str, market: str) -> str:
    """Karşılaştırma mesajı formatla."""
    if not comparison:
        return "❌ Karşılaştırma yapılamadı."
    
    lines = [
        f"🏦 <b>Broker Karşılaştırması: {symbol} ({market.upper()})</b>",
        f"📊 İşlem: {qty:.4f} lot @ {price:.2f} = {comparison[0]['gross_value']:,.2f} ₺",
        "",
    ]
    
    for c in comparison:
        medal = "🥇" if c["rank"] == 1 else ("🥈" if c["rank"] == 2 else ("🥉" if c["rank"] == 3 else f"{c['rank']}."))
        lines.append(
            f"{medal} <b>{c['broker']}</b>\n"
            f"   Komisyon: {c['commission']:,.2f} ₺ (%{c['commission_pct']:.3f})\n"
            f"   Toplam Maliyet: <b>{c['net_cost']:,.2f} ₺</b>"
            + (f"\n   Aylık ücret: {c['monthly_fee']:,.0f} ₺" if c.get('monthly_fee', 0) > 0 else "")
        )
    
    # En iyi vs en kötü fark
    best = comparison[0]
    worst = comparison[-1]
    saving = worst["net_cost"] - best["net_cost"]
    lines.append("")
    lines.append(f"💡 <b>Tasarruf:</b> {best['broker']} ile {worst['broker']} yerine {saving:,.2f} ₺ kazancınız olur.")
    
    return "\n".join(lines)


# Kullanıcı broker tercihi (database'e kaydedilecek)
DEFAULT_BROKER = "midas"  # Varsayılan


def get_user_broker(user_id: int) -> str:
    """Kullanıcının tercih ettiği broker (şimdilik varsayılan)."""
    # TODO: database'den oku
    return DEFAULT_BROKER


def set_user_broker(user_id: int, broker_key: str) -> bool:
    """Kullanıcı broker tercihini kaydet."""
    if broker_key.lower() in BROKERS:
        # TODO: database'e yaz
        return True
    return False