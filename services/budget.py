"""Butce ve otomatik yatirim plani yonetimi."""
from datetime import datetime

from database import (
    add_expense,
    get_budget,
    get_expenses,
    get_expenses_by_category,
    get_transactions,
    set_budget,
)


def set_plan(user_id: int, salary: float, invest_amount: float,
             currency: str = "TRY") -> None:
    set_budget(user_id, salary, invest_amount, currency)


def record_expense(user_id: int, amount: float, category: str,
                   note: str = "") -> int:
    return add_expense(user_id, amount, category, note)


def month_str() -> str:
    return datetime.now().strftime("%Y-%m")


def get_month_report(user_id: int) -> dict:
    """Ay icin butce + harcama + yatirim raporu."""
    month = month_str()
    b = get_budget(user_id)
    expenses = get_expenses(user_id, month)
    by_cat = get_expenses_by_category(user_id, month)
    buys = [
        t for t in get_transactions(user_id, month=month) if t["side"] == "BUY"
    ]
    invested = sum(t["qty"] * t["price"] for t in buys)

    total_expense = sum(e["amount"] for e in expenses) if expenses else 0.0
    salary = float(b["salary"]) if b and b["salary"] else 0.0
    invest_target = float(b["invest_amount"]) if b and b["invest_amount"] else 0.0

    remaining = salary - total_expense - invested
    savings_rate = ((salary - total_expense) / salary * 100) if salary else 0.0
    invest_pct = (invested / invest_target * 100) if invest_target else 0.0

    return {
        "month": month,
        "salary": salary,
        "invest_target": invest_target,
        "invested": invested,
        "invest_pct": invest_pct,
        "total_expense": total_expense,
        "by_category": by_cat,
        "remaining": remaining,
        "savings_rate": savings_rate,
        "n_expenses": len(expenses),
        "n_buys": len(buys),
    }
