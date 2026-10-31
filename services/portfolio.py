"""Portfoy hesabi: FIFO maliyet bazli kar/zarar takibi (komisyon destekli)."""
from collections import deque
from dataclasses import dataclass

from database import add_transaction, get_transactions
from services import market_data as md


@dataclass
class Position:
    symbol: str
    currency: str
    qty: float = 0.0
    avg_cost: float = 0.0
    cost_basis: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pct: float = 0.0
    realized_pnl: float = 0.0
    total_commission: float = 0.0


def buy(user_id: int, symbol: str, qty: float, price: float, currency: str,
        note: str = "", commission: float = 0.0) -> int:
    """Alım kaydı (komisyon dahil)."""
    return add_transaction(user_id, symbol, "BUY", qty, price, currency, commission, note)


def sell(user_id: int, symbol: str, qty: float, price: float, currency: str,
         note: str = "", commission: float = 0.0) -> int:
    """Satım kaydı (komisyon dahil)."""
    return add_transaction(user_id, symbol, "SELL", qty, price, currency, commission, note)


def calculate_qty_from_amount(amount: float, price: float, commission: float = 0.0) -> float:
    """Verilen tutar ve fiyattan komisyon düşerek alabileceğin lot sayısını hesaplar.
    
    amount: Harcamak istediğin toplam tutar (komisyon dahil)
    price: Birim fiyat
    commission: Komisyon tutarı
    
    Returns: Alınabilecek lot adedi
    """
    net_amount = max(amount - commission, 0)
    if price <= 0:
        return 0.0
    return net_amount / price


def estimate_commission(value: float, rate: float = 0.001, min_commission: float = 1.0) -> float:
    """Tahmini komisyon hesaplar (varsayılan %0.1, min $1)."""
    return max(value * rate, min_commission)


def estimate_commission_for_symbol(sym: str, amount_try: float) -> dict:
    """
    Sembol için uygun komisyon hesaplar (TRY bütçesine göre).
    
    US hisseleri için: TRY -> USD çevir, USD komisyonu hesapla, TRY'ye çevir
    BIST/Kripto için: Doğrudan TRY'de hesapla
    
    Returns: {"commission_try": float, "commission_usd": float, "currency": "USD|TRY", "commission_pct": float}
    """
    from services import market_data as md
    
    kind = md.kind_of(sym)
    cur = "USD" if kind == "us" else ("TRY" if kind == "bist" else "USD")
    
    if amount_try <= 0:
        return {"commission_try": 0.0, "commission_usd": 0.0, "currency": cur, "commission_pct": 0.0}
    
    usd_try = md.get_fx_rate("TRY=X") or 32.0
    
    if cur == "USD":
        # US hisse: TRY bütçesini USD'ye çevir
        amount_usd = amount_try / usd_try
        commission_usd = estimate_commission(amount_usd, rate=0.001, min_commission=1.0)
        commission_try = commission_usd * usd_try
    else:
        # BIST/Kripto: Doğrudan TRY'de hesapla
        commission_try = estimate_commission(amount_try, rate=0.001, min_commission=5.0)
        commission_usd = commission_try / usd_try
    
    commission_pct = (commission_try / amount_try * 100) if amount_try > 0 else 0.0
    
    return {
        "commission_try": commission_try,
        "commission_usd": commission_usd,
        "currency": cur,
        "commission_pct": commission_pct,
    }


def _compute_positions(user_id: int) -> dict[str, Position]:
    """Islem gecmisinden mevcut pozisyonlari FIFO ile hesaplar (komisyon dahil)."""
    txns = get_transactions(user_id)
    lots: dict[str, deque] = {}
    positions: dict[str, Position] = {}

    for t in txns:
        sym = t["symbol"]
        pos = positions.setdefault(sym, Position(symbol=sym, currency=t["currency"]))
        # sqlite3.Row doesn't have .get(), use direct access with fallback
        try:
            commission = t["commission"]
        except (KeyError, IndexError):
            commission = 0.0
        commission = commission or 0.0
        if t["side"] == "BUY":
            lots.setdefault(sym, deque()).append((t["qty"], t["price"], commission))
            pos.qty += t["qty"]
            pos.cost_basis += t["qty"] * t["price"] + commission
            pos.total_commission += commission
            pos.avg_cost = pos.cost_basis / pos.qty if pos.qty else 0.0
        else:  # SELL
            remaining = t["qty"]
            sell_commission = commission
            while remaining > 1e-9 and lots.get(sym):
                lot_qty, lot_price, lot_commission = lots[sym][0]
                take = min(remaining, lot_qty)
                # Komisyonu orantılı dağıt
                prop_commission = sell_commission * (take / t["qty"]) if t["qty"] > 0 else 0
                pos.realized_pnl += take * (t["price"] - lot_price) - prop_commission
                remaining -= take
                if take >= lot_qty - 1e-9:
                    lots[sym].popleft()
                else:
                    lots[sym][0] = (lot_qty - take, lot_price, lot_commission)
            pos.qty -= t["qty"]
            pos.total_commission += sell_commission
            pos.cost_basis = sum(q * p + c for q, p, c in lots.get(sym, []))
            pos.avg_cost = pos.cost_basis / pos.qty if pos.qty > 1e-9 else 0.0

    # Sifir pozisyonlari temizle (tamamen satildi)
    for sym in list(positions.keys()):
        if positions[sym].qty <= 1e-9:
            del positions[sym]

    return positions


def get_portfolio(user_id: int) -> dict:
    """Portfoy ozeti. Pozisyonlar + para birimi bazli toplamlar."""
    positions = _compute_positions(user_id)
    if not positions:
        return {"positions": [], "total_by_currency": {}, "grand_total": 0.0}

    symbols = list(positions.keys())
    quotes = md.get_quotes_batch(symbols)

    result: list[Position] = []
    total_by_currency: dict[str, float] = {}
    for sym, pos in positions.items():
        q = quotes.get(sym)
        if q:
            pos.current_price = q["price"]
            pos.currency = q["currency"]
        else:
            pos.current_price = pos.avg_cost
        pos.market_value = pos.qty * pos.current_price
        pos.unrealized_pnl = pos.market_value - pos.cost_basis
        pos.unrealized_pct = (pos.unrealized_pnl / pos.cost_basis * 100) if pos.cost_basis else 0.0
        total_by_currency[pos.currency] = total_by_currency.get(pos.currency, 0.0) + pos.market_value
        result.append(pos)

    result.sort(key=lambda p: p.market_value, reverse=True)
    return {
        "positions": result,
        "total_by_currency": total_by_currency,
        "grand_total": sum(total_by_currency.values()),
    }