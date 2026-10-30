"""Veritabani katmani — SQLite (yerel) ve PostgreSQL (bulut) destegi.

DATABASE_URL ortam degiskeni set ise PostgreSQL (Neon/Supabase/Render DB),
degilse yerel SQLite (finance.db) kullanilir. Ayni fonksiyon API'si ikisinde
de gecerli oldugundan uygulama kodu fark etmeden calisir.

Tablo:
- users        : yetkili kullanicilar
- watchlist    : takip listesi (izlenen hisseler)
- transactions : portfoy islemleri (alis/satis)
- budgets      : maas + aylik yatirim hedefi
- expenses     : harcamalar (kategori bazli)
- alerts       : fiyat alarmlari
- user_plan    : asistan plani (maas bolumu)
- pending_expense : aksam kontrolunde bekleyen harcama giris
"""
import re
import sqlite3
import threading
from datetime import datetime

import config

_use_pg = bool(config.DATABASE_URL)
_lock = threading.Lock()

if _use_pg:
    import psycopg
    from psycopg.rows import dict_row
else:
    psycopg = None  # type: ignore[assignment]


# PRIMARY KEY'i 'id' degil baska sutun olan tablolar (INSERT sonrasi dondurulecek sutun)
_PG_ID_COL = {
    "users": "user_id",
    "budgets": "user_id",
    "user_plan": "user_id",
    "pending_expense": "user_id",
    "cash": "user_id",
    "tax_events": "id",
    "dividend_events": "id",
    "backups": "id",
    "portfolio_snapshots": "id",
    "notes": "id",
    "alert_config": "id",
    "corp_calendar": "id",
    "user_webhooks": "id",
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    symbol      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
    qty         REAL NOT NULL,
    price       REAL NOT NULL,
    currency    TEXT NOT NULL,
    commission  REAL DEFAULT 0,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budgets (
    user_id      INTEGER PRIMARY KEY,
    salary       REAL,
    invest_amount REAL,
    currency     TEXT DEFAULT 'TRY',
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    amount      REAL NOT NULL,
    category    TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    symbol       TEXT NOT NULL,
    target_price REAL NOT NULL,
    direction    TEXT NOT NULL CHECK(direction IN ('above','below')),
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    triggered_at TEXT,
    webhook_url  TEXT,
    webhook_type TEXT
);

CREATE TABLE IF NOT EXISTS user_plan (
    user_id          INTEGER PRIMARY KEY,
    salary           REAL,
    expenses         REAL,
    risk             TEXT,
    goal             TEXT,
    salary_day       INTEGER,
    emergency_target REAL,
    emergency_saved  REAL DEFAULT 0,
    plan             TEXT,
    created_at       TEXT,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS pending_expense (
    user_id    INTEGER PRIMARY KEY,
    note       TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS tax_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    symbol     TEXT NOT NULL,
    event_type TEXT NOT NULL,
    qty        REAL NOT NULL,
    price      REAL NOT NULL,
    amount     REAL NOT NULL,
    fee        REAL DEFAULT 0,
    currency   TEXT DEFAULT 'TRY',
    event_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dividend_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    symbol     TEXT NOT NULL,
    gross_amount REAL NOT NULL,
    tax_withheld REAL DEFAULT 0,
    net_amount REAL NOT NULL,
    currency   TEXT DEFAULT 'TRY',
    ex_date    TEXT NOT NULL,
    pay_date   TEXT,
    drip_enabled INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    backup_type TEXT NOT NULL,
    gist_id    TEXT,
    file_size  INTEGER,
    checksum   TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    total_value   REAL NOT NULL,
    invested      REAL NOT NULL,
    cash          REAL NOT NULL,
    snapshot_date TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    symbol     TEXT NOT NULL,
    note       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_config (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    symbol          TEXT NOT NULL,
    type            TEXT NOT NULL,
    params          TEXT,
    active          INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    webhook_url     TEXT,
    webhook_type    TEXT
);

CREATE TABLE IF NOT EXISTS user_webhooks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    webhook_type    TEXT NOT NULL,
    webhook_url     TEXT NOT NULL,
    alarm_scope     TEXT DEFAULT 'all',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(user_id, webhook_type)
);

CREATE TABLE IF NOT EXISTS corp_calendar (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash (
    user_id    INTEGER PRIMARY KEY,
    balance    REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_txn_user   ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_exp_user   ON expenses(user_id);
CREATE INDEX IF NOT EXISTS idx_watch_user ON watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_alert_user ON alerts(user_id);
"""


# ---------------- Altyapi ----------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _pg_connect():
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)


def _pg_prepare(sql: str) -> str:
    """Postgres uyumlu hale getirir: ? -> %s, INSERT sonuna RETURNING <pk>.

    'id' sutunu olmayan tablolar (users, budgets...) icin anahtar sutun
    _PG_ID_COL'dan alinir, aksi halde varsayilan 'id' kullanilir.
    """
    s = sql.replace("?", "%s").strip().rstrip(";")
    m = re.search(r"INSERT INTO (\w+)", s, re.IGNORECASE)
    if m:
        col = _PG_ID_COL.get(m.group(1).lower(), "id")
        s += f" RETURNING {col}"
    return s


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    if _use_pg:
        conn = psycopg.connect(config.DATABASE_URL)
        try:
            cur = conn.cursor()
            for stmt in _SCHEMA.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                # PostgreSQL'de AUTOINCREMENT yoktur; SERIAL kullanilir
                stmt = stmt.replace(
                    "INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY"
                )
                cur.execute(stmt)
            conn.commit()
        finally:
            conn.close()
        return
    with _lock:
        conn = _conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """Yazma islemleri.

    INSERT  -> yeni satirin id'sini dondurur
    diger   -> etkilenen satir sayisini dondurur (rowcount)
    """
    if _use_pg:
        conn = _pg_connect()
        try:
            stmt = _pg_prepare(sql)
            cur = conn.execute(stmt, params)
            if stmt.lstrip().upper().startswith("INSERT"):
                row = cur.fetchone()
                conn.commit()
                if row is None:  # ON CONFLICT DO NOTHING nedeniyle ekleme yok
                    return 0
                # RETURNING ile donen anahtar sutunu (id veya user_id) al
                return int(list(row.values())[0])
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    with _lock:
        conn = _conn()
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            if sql.lstrip().upper().startswith("INSERT"):
                return cur.lastrowid
            return cur.rowcount
        finally:
            conn.close()


def query(sql: str, params: tuple = ()) -> list:
    if _use_pg:
        conn = _pg_connect()
        try:
            cur = conn.execute(sql.replace("?", "%s"), params)
            rows = cur.fetchall()
            conn.commit()
            return list(rows)
        finally:
            conn.close()
    conn = _conn()
    try:
        return list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()):
    if _use_pg:
        conn = _pg_connect()
        try:
            cur = conn.execute(sql.replace("?", "%s"), params)
            row = cur.fetchone()
            conn.commit()
            return row
        finally:
            conn.close()
    conn = _conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


# ---------------- Kullanicilar ----------------

def register_user(user_id: int, username: str = "", first_name: str = "") -> None:
    execute(
        "INSERT INTO users (user_id, username, first_name, created_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO NOTHING",
        (user_id, username or "", first_name or "", now_iso()),
    )


# ---------------- Takip listesi ----------------

def add_watch(user_id: int, symbol: str) -> bool:
    execute(
        "INSERT INTO watchlist (user_id, symbol, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, symbol) DO NOTHING",
        (user_id, symbol, now_iso()),
    )
    return True


def remove_watch(user_id: int, symbol: str) -> bool:
    cur_affected = execute(
        "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user_id, symbol)
    )
    return cur_affected > 0


def get_watchlist(user_id: int) -> list:
    return query(
        "SELECT symbol, created_at FROM watchlist WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    )


def get_all_watchlists() -> list:
    return query("SELECT DISTINCT user_id, symbol FROM watchlist ORDER BY user_id")


# ---------------- Islemler ----------------

def add_transaction(user_id: int, symbol: str, side: str, qty: float, price: float,
                    currency: str, commission: float = 0.0, note: str = "") -> int:
    return execute(
        "INSERT INTO transactions (user_id, symbol, side, qty, price, currency, commission, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, symbol, side, qty, price, currency, commission, note or "", now_iso()),
    )


def get_transactions(user_id: int, symbol: str | None = None,
                     month: str | None = None) -> list:
    sql = "SELECT * FROM transactions WHERE user_id = ?"
    params: list = [user_id]
    if symbol:
        sql += " AND symbol = ?"
        params.append(symbol)
    if month:
        sql += " AND substr(created_at, 1, 7) = ?"
        params.append(month)
    sql += " ORDER BY created_at"
    return query(sql, tuple(params))


def get_transaction_symbols(user_id: int) -> list[str]:
    rows = query(
        "SELECT DISTINCT symbol FROM transactions WHERE user_id = ?", (user_id,)
    )
    return [r["symbol"] for r in rows]


# ---------------- Butce ----------------

def set_budget(user_id: int, salary: float, invest_amount: float, currency: str = "TRY") -> None:
    execute(
        "INSERT INTO budgets (user_id, salary, invest_amount, currency, updated_at) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "salary = excluded.salary, invest_amount = excluded.invest_amount, "
        "currency = excluded.currency, updated_at = excluded.updated_at",
        (user_id, salary, invest_amount, currency, now_iso()),
    )


def get_budget(user_id: int):
    return query_one("SELECT * FROM budgets WHERE user_id = ?", (user_id,))


def add_expense(user_id: int, amount: float, category: str, note: str = "") -> int:
    return execute(
        "INSERT INTO expenses (user_id, amount, category, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, note or "", now_iso()),
    )


def get_expenses(user_id: int, month: str | None = None) -> list:
    sql = "SELECT * FROM expenses WHERE user_id = ?"
    params: list = [user_id]
    if month:
        sql += " AND substr(created_at, 1, 7) = ?"
        params.append(month)
    sql += " ORDER BY created_at DESC"
    return query(sql, tuple(params))


def get_expenses_by_category(user_id: int, month: str) -> list:
    return query(
        "SELECT category, SUM(amount) AS total, COUNT(*) AS cnt "
        "FROM expenses WHERE user_id = ? AND substr(created_at, 1, 7) = ? "
        "GROUP BY category ORDER BY total DESC",
        (user_id, month),
    )


# ---------------- Alarmlar ----------------

def add_alert(user_id: int, symbol: str, target_price: float, direction: str,
              webhook_url: str = "", webhook_type: str = "") -> int:
    return execute(
        "INSERT INTO alerts (user_id, symbol, target_price, direction, active, created_at, webhook_url, webhook_type) "
        "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
        (user_id, symbol, target_price, direction, now_iso(), webhook_url, webhook_type),
    )


def get_alerts(user_id: int | None = None, active_only: bool = False) -> list:
    sql = "SELECT * FROM alerts"
    params: list = []
    where = []
    if user_id is not None:
        where.append("user_id = ?")
        params.append(user_id)
    if active_only:
        where.append("active = 1")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    return query(sql, tuple(params))


def deactivate_alert(alert_id: int, user_id: int) -> bool:
    cur = execute(
        "UPDATE alerts SET active = 0, triggered_at = ? WHERE id = ? AND user_id = ?",
        (now_iso(), alert_id, user_id),
    )
    return cur > 0


def delete_alert(alert_id: int, user_id: int) -> bool:
    cur = execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))
    return cur > 0


# ---------------- Kullanici plani (asistan) ----------------

def set_user_plan(user_id: int, salary: float, expenses: float, risk: str, goal: str,
                  salary_day: int, emergency_target: float, plan_json: str) -> None:
    execute(
        "INSERT INTO user_plan (user_id, salary, expenses, risk, goal, salary_day, "
        "emergency_target, emergency_saved, plan, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "salary = excluded.salary, expenses = excluded.expenses, risk = excluded.risk, "
        "goal = excluded.goal, salary_day = excluded.salary_day, "
        "emergency_target = excluded.emergency_target, plan = excluded.plan, "
        "updated_at = excluded.updated_at",
        (user_id, salary, expenses, risk, goal, salary_day, emergency_target,
         plan_json, now_iso(), now_iso()),
    )


def get_user_plan(user_id: int):
    return query_one("SELECT * FROM user_plan WHERE user_id = ?", (user_id,))


def add_emergency_savings(user_id: int, amount: float) -> None:
    execute(
        "UPDATE user_plan SET emergency_saved = emergency_saved + ?, updated_at = ? "
        "WHERE user_id = ?",
        (amount, now_iso(), user_id),
    )


# ---------------- Bekleyen harcama giris (akşam kontrolu) ----------------

def set_pending_expense(user_id: int, note: str = "1") -> None:
    execute(
        "INSERT INTO pending_expense (user_id, note, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET note = excluded.note",
        (user_id, note, now_iso()),
    )


def clear_pending_expense(user_id: int) -> None:
    execute("DELETE FROM pending_expense WHERE user_id = ?", (user_id,))


def has_pending_expense(user_id: int) -> bool:
    row = query_one("SELECT 1 FROM pending_expense WHERE user_id = ?", (user_id,))
    return row is not None


# ---------------- Vergi / İşlem olayları ----------------

def add_tax_event(user_id: int, symbol: str, event_type: str, qty: float, price: float,
                  amount: float, fee: float = 0.0, currency: str = "TRY",
                  event_date: str | None = None) -> int:
    return execute(
        "INSERT INTO tax_events (user_id, symbol, event_type, qty, price, amount, fee, currency, event_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, symbol, event_type, qty, price, amount, fee, currency,
         event_date or now_iso(), now_iso()),
    )


def get_tax_events(user_id: int, year: int | None = None) -> list:
    if year:
        return query(
            "SELECT * FROM tax_events WHERE user_id = ? AND substr(event_date, 1, 4) = ? ORDER BY event_date",
            (user_id, str(year)),
        )
    return query(
        "SELECT * FROM tax_events WHERE user_id = ? ORDER BY event_date", (user_id,)
    )


# ---------------- Temettü olayları ----------------

def add_dividend_event(user_id: int, symbol: str, gross_amount: float,
                       tax_withheld: float, net_amount: float, currency: str,
                       ex_date: str, pay_date: str | None = None,
                       drip_enabled: int = 0) -> int:
    return execute(
        "INSERT INTO dividend_events (user_id, symbol, gross_amount, tax_withheld, net_amount, currency, ex_date, pay_date, drip_enabled, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, symbol, gross_amount, tax_withheld, net_amount, currency, ex_date,
         pay_date, drip_enabled, now_iso()),
    )


def get_dividend_events(user_id: int, symbol: str | None = None, year: int | None = None) -> list:
    sql = "SELECT * FROM dividend_events WHERE user_id = ?"
    params = [user_id]
    if symbol:
        sql += " AND symbol = ?"
        params.append(symbol)
    if year:
        sql += " AND substr(ex_date, 1, 4) = ?"
        params.append(str(year))
    sql += " ORDER BY ex_date"
    return query(sql, tuple(params))


# ---------------- Yedekler ----------------

def add_backup_record(user_id: int, backup_type: str, gist_id: str = "",
                      file_size: int = 0, checksum: str = "") -> int:
    return execute(
        "INSERT INTO backups (user_id, backup_type, gist_id, file_size, checksum, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, backup_type, gist_id, file_size, checksum, now_iso()),
    )


def get_backups(user_id: int, limit: int = 10) -> list:
    return query(
        "SELECT * FROM backups WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )


# ---------------- Portföy anlık görüntüleri ----------------

def add_portfolio_snapshot(user_id: int, total_value: float, invested: float,
                           cash: float, snapshot_date: str | None = None) -> int:
    return execute(
        "INSERT INTO portfolio_snapshots (user_id, total_value, invested, cash, snapshot_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, total_value, invested, cash, snapshot_date or now_iso(), now_iso()),
    )


def get_portfolio_snapshots(user_id: int, days: int = 365) -> list:
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=days)).isoformat()
    return query(
        "SELECT * FROM portfolio_snapshots WHERE user_id = ? AND snapshot_date >= ? ORDER BY snapshot_date",
        (user_id, start),
    )


# ---------------- Notlar ----------------

def add_note(user_id: int, symbol: str, note: str) -> int:
    return execute(
        "INSERT INTO notes (user_id, symbol, note, created_at) VALUES (?, ?, ?, ?)",
        (user_id, symbol, note, now_iso()),
    )


def get_notes(user_id: int, symbol: str | None = None) -> list:
    if symbol:
        return query(
            "SELECT * FROM notes WHERE user_id = ? AND symbol = ? ORDER BY created_at DESC",
            (user_id, symbol),
        )
    return query(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
    )


def delete_note(note_id: int, user_id: int) -> bool:
    cur = execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    return cur > 0


# ---------------- Gelişmiş alarmlar ----------------

def add_alert_config(user_id: int, symbol: str, type_: str, params: str = "",
                     webhook_url: str = "", webhook_type: str = "") -> int:
    return execute(
        "INSERT INTO alert_config (user_id, symbol, type, params, active, created_at, webhook_url, webhook_type) "
        "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
        (user_id, symbol, type_, params, now_iso(), webhook_url, webhook_type),
    )


def get_alert_configs(user_id: int, symbol: str | None = None, active_only: bool = True) -> list:
    sql = "SELECT * FROM alert_config WHERE user_id = ?"
    params = [user_id]
    if symbol:
        sql += " AND symbol = ?"
        params.append(symbol)
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY created_at DESC"
    return query(sql, tuple(params))


def deactivate_alert_config(config_id: int, user_id: int) -> bool:
    cur = execute(
        "UPDATE alert_config SET active = 0 WHERE id = ? AND user_id = ?",
        (config_id, user_id),
    )
    return cur > 0


# ---------------- Kurumsal takvim ----------------

def add_corp_event(symbol: str, event_type: str, event_date: str, details: str = "") -> int:
    return execute(
        "INSERT INTO corp_calendar (symbol, event_type, event_date, details, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (symbol, event_type, event_date, details, now_iso()),
    )


def get_corp_calendar(days_ahead: int = 30) -> list:
    from datetime import date, timedelta
    end = date.today() + timedelta(days=days_ahead)
    return query(
        "SELECT * FROM corp_calendar WHERE date(event_date) BETWEEN date('now') AND date(?) "
        "ORDER BY event_date",
        (end.isoformat(),),
    )


def get_corp_calendar_for_symbol(symbol: str) -> list:
    return query(
        "SELECT * FROM corp_calendar WHERE symbol = ? ORDER BY event_date",
        (symbol,),
    )


# ---------------- Nakit hesabi (eldeki para) ----------------

def get_cash(user_id: int) -> float:
    row = query_one("SELECT balance FROM cash WHERE user_id = ?", (user_id,))
    return float(row["balance"]) if row else 0.0


def add_cash(user_id: int, amount: float) -> float:
    """Nakti gunceller. Yeni bakiyeyi dondurur."""
    execute(
        "INSERT INTO cash (user_id, balance, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "balance = cash.balance + excluded.balance, updated_at = excluded.updated_at",
        (user_id, amount, now_iso()),
    )
    return get_cash(user_id)


def set_cash(user_id: int, amount: float) -> float:
    """Nakti dogrudan ayarlar (baslangic bakiyesi / duzeltme)."""
    execute(
        "INSERT INTO cash (user_id, balance, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "balance = excluded.balance, updated_at = excluded.updated_at",
        (user_id, amount, now_iso()),
    )
    return get_cash(user_id)


def reset_user_data(user_id: int, keep_budget: bool = True, keep_cash: bool = True) -> dict:
    """Kullanicinin portfoy/watchlist/alarm verilerini temizler.
    
    Args:
        user_id: Kullanici ID
        keep_budget: True ise butce (maas/yatirim) ve user_plan korunur
        keep_cash: True ise nakit bakiyesi korunur
    
    Returns:
        Silinen satir sayilari sozlugu
    """
    counts = {}
    
    # Temizlenecek tablolar (portfoy/takip/alarm odakli)
    tables_to_clear = [
        ("transactions", "DELETE FROM transactions WHERE user_id = ?"),
        ("watchlist", "DELETE FROM watchlist WHERE user_id = ?"),
        ("alerts", "DELETE FROM alerts WHERE user_id = ?"),
        ("alert_config", "DELETE FROM alert_config WHERE user_id = ?"),
        ("portfolio_snapshots", "DELETE FROM portfolio_snapshots WHERE user_id = ?"),
        ("tax_events", "DELETE FROM tax_events WHERE user_id = ?"),
        ("dividend_events", "DELETE FROM dividend_events WHERE user_id = ?"),
        ("notes", "DELETE FROM notes WHERE user_id = ?"),
        ("pending_expense", "DELETE FROM pending_expense WHERE user_id = ?"),
        ("backups", "DELETE FROM backups WHERE user_id = ?"),
    ]
    
    for name, sql in tables_to_clear:
        counts[name] = execute(sql, (user_id,))
    
    # Opsiyonel: butce ve nakit
    if not keep_budget:
        counts["budgets"] = execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
        counts["user_plan"] = execute("DELETE FROM user_plan WHERE user_id = ?", (user_id,))
        counts["expenses"] = execute("DELETE FROM expenses WHERE user_id = ?", (user_id,))
    
    if not keep_cash:
        counts["cash"] = execute("DELETE FROM cash WHERE user_id = ?", (user_id,))
    
    return counts
