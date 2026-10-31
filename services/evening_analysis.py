"""Akşam analizi ve al/sat öneri motoru.

Her akşam portföyü analiz eder, broker maliyetlerini hesaplar,
sinyalleri değerlendirip "bugün ne yapmalı?" önerisi üretir.
"""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from database import get_transactions, get_user_plan, get_cash
from services import market_data as md, signals, portfolio, broker, assistant
from services.broker import Market, compare_brokers, format_comparison, get_user_broker


@dataclass
class EveningAction:
    """Akşam eylem önerisi."""
    symbol: str
    action: str  # BUY, SELL, HOLD, WATCH
    reason: str
    qty_suggestion: float = 0.0
    price_target: float = 0.0
    stop_loss: float = 0.0
    broker_cost: float = 0.0


def analyze_portfolio_for_evening(user_id: int) -> dict:
    """Portföyü akşam analizi için hazırlar."""
    # Portföy pozisyonları
    pf = portfolio.get_portfolio(user_id)
    positions = pf["positions"]
    
    # Nakit durumu
    cash = get_cash(user_id)
    
    # Plan (varsa)
    plan_row = get_user_plan(user_id)
    plan = assistant.plan_from_json(plan_row["plan"]) if plan_row else None
    
    # Kullanıcının broker'ı
    user_broker = get_user_broker(user_id)
    
    # Takip listesi
    from database import get_watchlist
    watch = get_watchlist(user_id)
    watch_symbols = [w["symbol"] for w in watch]
    
    return {
        "positions": positions,
        "cash": cash,
        "plan": plan,
        "broker": user_broker,
        "watch_symbols": watch_symbols,
    }


def get_sell_candidates(analysis: dict) -> list[EveningAction]:
    """Satılabilecek pozisyonları tespit et."""
    actions = []
    positions = analysis["positions"]
    broker_key = analysis["broker"]
    
    for pos in positions:
        sym = pos.symbol
        kind = md.kind_of(sym)
        market = Market.BIST if kind == "bist" else (Market.US if kind == "us" else Market.CRYPTO)
        fx_rate = md.get_fx_rate("TRY=X") or 32.0  # fallback
        
        # Sinyal kontrol
        sig = signals.score_symbol(sym)
        if not sig:
            continue
        
        # Satım sinyali mi?
        if sig["score"] <= -3:  # SAT veya GÜÇLÜ SAT
            # Komisyon maliyeti
            cost_info = broker.calculate_total_cost(broker_key, market, pos.qty, pos.current_price, fx_rate)
            sell_comm = cost_info.get("commission", 0)
            
            actions.append(EveningAction(
                symbol=sym,
                action="SELL",
                reason=f"Sinyal: {sig['signal']} (skor {sig['score']:+d}), RSI {sig['rsi']:.0f}, {sig['reasons'][0] if sig['reasons'] else ''}",
                qty_suggestion=pos.qty,
                price_target=pos.current_price,
                stop_loss=sig.get("stop", 0),
                broker_cost=sell_comm,
            ))
        
        # Stop-loss tetiklendi mi?
        elif pos.unrealized_pct <= -8:  # %8 altı
            cost_info = broker.calculate_total_cost(broker_key, market, pos.qty, pos.current_price, fx_rate)
            sell_comm = cost_info.get("commission", 0)
            
            actions.append(EveningAction(
                symbol=sym,
                action="SELL",
                reason=f"⚠️ Stop-loss: %{pos.unrealized_pct:.1f} zarar. Koruma satışı önerilir.",
                qty_suggestion=pos.qty,
                price_target=pos.current_price,
                stop_loss=pos.current_price,
                broker_cost=sell_comm,
            ))
    
    return actions


def get_buy_candidates(analysis: dict) -> list[EveningAction]:
    """Alınabilecek fırsatları tespit et."""
    actions = []
    watch_symbols = analysis["watch_symbols"]
    cash = analysis["cash"]
    plan = analysis["plan"]
    broker_key = analysis["broker"]
    
    if not watch_symbols:
        return actions
    
    # Sinyal taraması
    scan_results = signals.scan_symbols(watch_symbols)
    
    # Plan yatırım bütçesi
    invest_budget = plan["invest_share"] if plan else cash * 0.2
    available_cash = min(cash, invest_budget)
    
    for sig in scan_results:
        if sig["score"] >= 3:  # AL veya GÜÇLÜ AL
            sym = sig["symbol"]
            kind = md.kind_of(sym)
            market = Market.BIST if kind == "bist" else (Market.US if kind == "us" else Market.CRYPTO)
            fx_rate = md.get_fx_rate("TRY=X") or 32.0
            
            # Ne kadar alabiliriz?
            price = sig["price"]
            cost_info = broker.calculate_total_cost(broker_key, market, 1, price, fx_rate)
            per_lot_cost = cost_info["net_cost"]
            
            max_qty = available_cash / per_lot_cost if per_lot_cost > 0 else 0
            suggested_qty = min(max_qty, available_cash / per_lot_cost * 0.5)  # Yarısını ayır
            
            if suggested_qty > 0:
                actions.append(EveningAction(
                    symbol=sym,
                    action="BUY",
                    reason=f"Sinyal: {sig['signal']} (skor {sig['score']:+d}), RSI {sig['rsi']:.0f}, {sig['reasons'][0] if sig['reasons'] else ''}",
                    qty_suggestion=suggested_qty,
                    price_target=price,
                    stop_loss=sig.get("stop", 0),
                    broker_cost=cost_info["commission"] * suggested_qty,
                ))
                available_cash -= suggested_qty * per_lot_cost
    
    return actions


def generate_evening_report(user_id: int) -> str:
    """Akşam raporu üret."""
    analysis = analyze_portfolio_for_evening(user_id)
    
    sells = get_sell_candidates(analysis)
    buys = get_buy_candidates(analysis)
    
    pf = portfolio.get_portfolio(user_id)
    cash = analysis["cash"]
    total_value = cash + sum(p.market_value for p in pf["positions"])
    
    lines = [
        f"🌙 <b>Akşam Analizi — {datetime.now(md.TZ_ISTANBUL):%d %B %Y}</b>",
        f"💰 Nakit: {cash:,.2f} ₺ | 📈 Portföy: {sum(p.market_value for p in pf['positions']):,.2f} ₺",
        f"🏦 Toplam: <b>{total_value:,.2f} ₺</b>",
        f"🏛️ Broker: {analysis['broker'].upper()}",
        "",
    ]
    
    # Satış önerileri
    if sells:
        lines.append("🔴 <b>Satış Önerileri:</b>")
        for a in sells:
            # Komisyon para birimi belirle
            kind = md.kind_of(a.symbol)
            cur = "$" if kind == "us" else "₺"
            comm_val = a.broker_cost if kind == "us" else a.broker_cost
            lines.append(
                f"  • <b>{a.symbol}</b> — {a.action}\n"
                f"    Miktar: {a.qty_suggestion:.4f} @ ~{a.price_target:.2f}\n"
                f"    Sebep: {a.reason}\n"
                f"    Komisyon: ~{comm_val:.2f} {cur}"
            )
    else:
        lines.append("🟢 <b>Satış önerisi yok</b> — Pozisyonlar koruma bandında.")
    
    lines.append("")
    
    # Alım önerileri
    if buys:
        lines.append("🟢 <b>Alım Fırsatları:</b>")
        for a in buys[:5]:  # En fazla 5
            kind = md.kind_of(a.symbol)
            cur = "$" if kind == "us" else "₺"
            comm_val = a.broker_cost if kind == "us" else a.broker_cost
            lines.append(
                f"  • <b>{a.symbol}</b> — {a.action}\n"
                f"    Önerilen: {a.qty_suggestion:.4f} lot @ ~{a.price_target:.2f}\n"
                f"    Sebep: {a.reason}\n"
                f"    Komisyon: ~{comm_val:.2f} {cur}"
            )
    else:
        lines.append("🔵 <b>Alım fırsatı yok</b> — Sinyaller zayıf veya nakit yetersiz.")
    
    lines.append("")
    lines.append("💡 <b>Özet:</b> ")
    if sells and buys:
        lines.append("Hem satış hem alım var — portföy dengeleme günü.")
    elif sells:
        lines.append("Sadece satış — nakit biriktir, fırsat bekle.")
    elif buys:
        lines.append("Sadece alım — fırsatlar var, nakit çalıştır.")
    else:
        lines.append("Bekle — piyasa karar verme aşamasında.")
    
    lines.append("")
    lines.append("⚠️ <i>Bu öneriler algoritmiktir, yatırım tavsiyesi değildir. Kendi kararın ver.</i>")
    
    return "\n".join(lines)


def get_broker_comparison_for_user(user_id: int, symbol: str) -> str:
    """Kullanıcının broker'ı vs alternatifler için maliyet karşılaştırması."""
    analysis = analyze_portfolio_for_evening(user_id)
    broker_key = analysis["broker"]
    
    resolved = md.resolve_symbol(symbol)
    if not resolved:
        return "Sembol bulunamadı."
    
    sym = resolved[0]
    kind = md.kind_of(sym)
    market = Market.BIST if kind == "bist" else (Market.US if kind == "us" else Market.CRYPTO)
    
    # Mevcut pozisyon varsa onun miktarını kullan, yoksa 1 lot varsay
    pos_qty = 1.0
    for p in analysis["positions"]:
        if p.symbol == sym:
            pos_qty = p.qty
            break
    
    price_info = md.get_quote(sym)
    if not price_info:
        return "Fiyat alınamadı."
    
    price = price_info["price"]
    fx_rate = md.get_fx_rate("TRY=X") or 32.0
    
    comparison = compare_brokers(market, pos_qty, price, fx_rate)
    return format_comparison(comparison, sym, kind)