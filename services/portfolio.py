"""Portfoy hesabi: FIFO maliyet bazli kar/zarar takibi."""
from collections import deque
from dataclasses import dataclass, field

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


def buy(user_id: int, symbol: str, qty: float, price: float, currency: str,
        note: str = "") -> int:
    return add_transaction(user_id, symbol, "BUY", qty, price, currency, note)


def sell(user_id: int, symbol: str, qty: float, price: float, currency: str,
         note: str = "") -> int:
    return add_transaction(user_id, symbol, "SELL", qty, price, currency, note)


def _compute_positions(user_id: int) -> dict[str, Position]:
    """Islem gecmisinden mevcut pozisyonlari FIFO ile hesaplar."""
    txns = get_transactions(user_id)
    lots: dict[str, deque] = {}
    positions: dict[str, Position] = {}

    for t in txns:
        sym = t["symbol"]
        pos = positions.setdefault(sym, Position(symbol=sym, currency=t["currency"]))
        if t["side"] == "BUY":
            lots.setdefault(sym, deque()).append((t["qty"], t["price"]))
            pos.qty += t["qty"]
            pos.cost_basis += t["qty"] * t["price"]
            pos.avg_cost = pos.cost_basis / pos.qty if pos.qty else 0.0
        else:  # SELL
            remaining = t["qty"]
            while remaining > 1e-9 and lots.get(sym):
                lot_qty, lot_price = lots[sym][0]
                take = min(remaining, lot_qty)
                pos.realized_pnl += take * (t["price"] - lot_price)
                remaining -= take
                if take >= lot_qty - 1e-9:
                    lots[sym].popleft()
                else:
                    lots[sym][0] = (lot_qty - take, lot_price)
            pos.qty -= t["qty"]
            pos.cost_basis = sum(q * p for q, p in lots.get(sym, []))
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
            pos.current_price = pos.avg_cost  # fiyat alinamazsa maliyetle degerle
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
