"""Smoke test: bot token olmadan tum cekirdek mantigi dogrular."""
import os

# .env icindeki ayarlari gormezden gel (test veritabani kullan)
_TEST_DB = os.path.join(os.path.dirname(__file__), "test_finance.db")
os.environ["DB_PATH"] = _TEST_DB
if os.path.exists(_TEST_DB):
    os.remove(_TEST_DB)  # her calistirmada temiz basla

from database import init_db, get_transactions
from services import budget, indicators as ind, market_data as md, portfolio, signals
from services import alerts as alert_svc

init_db()  # tablolari olustur

USER = 12345
FAIL = []


def check(name, cond, extra=""):
    status = "OK " if cond else "FAIL"
    # Konsol kodlamasi Turkce/emoji karakterlerini basamayabilir (ornek: cp950)
    line = f"  [{status}] {name}" + (f"  {extra}" if extra else "")
    safe = line.encode("ascii", "replace").decode("ascii")
    print(safe)
    if not cond:
        FAIL.append(name)


def main():
    print("== Sembol cozumleme ==")
    for raw, expect_kind in [("THYAO", "bist"), ("AAPL", "us"), ("BTC", "crypto"),
                             ("XU100", "bist"), ("USD", "fx"), ("GARAN", "bist")]:
        res = md.resolve_symbol(raw)
        check(f"{raw} -> {res}", res is not None and res[1] == expect_kind,
              str(res) if res else "YOK")

    print("== Fiyat verisi ==")
    q = md.get_quote("THYAO.IS")
    check("get_quote THYAO", q and q["price"] > 0 and q["currency"] == "TRY", str(q))
    batch = md.get_quotes_batch(["THYAO.IS", "AAPL", "BTC-USD", "XU100.IS"])
    check("get_quotes_batch (4 sembol)", len(batch) >= 3, f"{len(batch)}/{4} alindi")

    print("== Indikatorler ==")
    df = md.get_history("AAPL")
    a = ind.full_analysis(df)
    check("full_analysis", a["rsi"] > 0 and a["sma20"] > 0 and a["atr"] > 0,
          f"RSI={a['rsi']:.1f} ATR={a['atr']:.2f}")
    check("rsi_label", ind.rsi_label(30) == "Aşırı satım")

    print("== Sinyal motoru ==")
    sig = signals.score_symbol("AAPL")
    check("score_symbol AAPL", sig is not None and "signal" in sig, str(sig["signal"]) if sig else "")
    sigs = signals.scan_symbols(["THYAO.IS", "AAPL", "BTC-USD", "XU100.IS"])
    check("scan_symbols (4)", len(sigs) >= 3, f"{len(sigs)} sinyal")

    print("== Portfoy (FIFO) ==")
    portfolio.buy(USER, "THYAO.IS", 100, 200, "TRY")
    portfolio.buy(USER, "THYAO.IS", 100, 250, "TRY")
    portfolio.sell(USER, "THYAO.IS", 100, 300, "TRY")  # ilk 100 lotu 200'den satar
    pf = portfolio.get_portfolio(USER)
    check("FIFO kalan 100 lot", pf["positions"] and pf["positions"][0].qty == 100,
          f"qty={pf['positions'][0].qty if pf['positions'] else 0}")
    check("FIFO gerceklesen +10000", abs(pf["positions"][0].realized_pnl - 10000) < 1,
          f"realized={pf['positions'][0].realized_pnl:.2f}")

    print("== Butce ==")
    budget.set_plan(USER, 50000, 10000)
    budget.record_expense(USER, 3000, "market")
    budget.record_expense(USER, 1500, "fatura")
    rep = budget.get_month_report(USER)
    check("butce maas/harcama", rep["salary"] == 50000 and rep["total_expense"] == 4500,
          f"harcama={rep['total_expense']}")
    check("tasarruf orani", abs(rep["savings_rate"] - 91.0) < 0.01, f"%{rep['savings_rate']:.1f}")

    print("== Alarm ==")
    from database import add_alert, get_alerts
    add_alert(USER, "AAPL", 1.0, "above")  # su anki fiyatin cok altinda -> aninda tetiklenir
    triggered = alert_svc.check_all_alerts()
    check("alarm tetikleme", any(t["user_id"] == USER for t in triggered),
          f"{len(triggered)} tetiklendi")
    check("alarm tek seferlik", get_alerts(USER, active_only=True) == [])

    print("== Islem gecmisi ==")
    txns = get_transactions(USER)
    check("3 islem kaydi", len(txns) == 3, f"{len(txns)} islem")

    print("== Asistan plani ==")
    from services import assistant
    plan = assistant.build_plan(50000, 25000, "dengeli", "acil_fon", 5)
    check("plan maas bolunmesi", abs(plan["needs"] - 25000) < 1 and abs(plan["wants"] - 15000) < 1
          and abs(plan["savings"] - 10000) < 1,
          f"needs={plan['needs']} wants={plan['wants']} savings={plan['savings']}")
    check("acil fon hedefi 6 ay", abs(plan["emergency_target"] - 150000) < 1, str(plan["emergency_target"]))
    check("acil fon payi %50", abs(plan["emergency_share"] - 5000) < 1, str(plan["emergency_share"]))
    check("yatirim dagilimi", len(plan["suggestions"]) == 3, f"{len(plan['suggestions'])} oneri")
    check("gider uyarisi", assistant.build_plan(50000, 40000, "sakin", "emeklilik", 10)["warning"] is not None)

    # uç durum: giderler maaşı aşarsa
    p2 = assistant.build_plan(30000, 60000, "sakin", "kisa_vade", 1)
    check("gider>maas uyarisi", p2["warning"] is not None and p2["needs"] <= p2["salary"], str(p2["warning"]))

    from database import set_user_plan, get_user_plan, add_emergency_savings
    set_user_plan(USER, plan["salary"], plan["expenses"], plan["risk"], plan["goal"],
                  plan["salary_day"], plan["emergency_target"], assistant.plan_to_json(plan))
    row = get_user_plan(USER)
    check("plan kaydedildi", row is not None and row["risk"] == "dengeli")
    add_emergency_savings(USER, 5000)
    check("acil fon birikimi", get_user_plan(USER)["emergency_saved"] == 5000)
    check("describe_plan", "Senin Planın" in assistant.describe_plan(plan, 5000))
    check("tip_of_day", isinstance(assistant.tip_of_day(), str) and len(assistant.tip_of_day()) > 10)
    check("today_action", "Bugün için önerim" in assistant.today_action(plan, 5000, 0, 10000))

    print("== Grafik ==")
    from services import charts
    img = charts.build_chart("AAPL", "3mo")
    check("build_chart PNG", img is not None and img[:8] == b"\x89PNG\r\n\x1a\n", f"{len(img) if img else 0} byte")
    check("build_chart az veri -> None", charts.build_chart("AAPL", "1d") is None)

    print("== Dogal dil ==")
    from services import nlp
    cases = {
        "BTC ne durumda?": ("price", "BTC-USD"),
        "THYAO alınır mı?": ("signal", "THYAO.IS"),
        "bu ay ne kadar harcadım?": ("expense", None),
        "portföyüm nasıl?": ("portfolio", None),
        "ne almalıyım?": ("signals", None),
        "bana bir şey öğret": ("tip", None),
        "planımı göster": ("plan", None),
    }
    for text, (want_action, want_sym) in cases.items():
        p = nlp.parse(text)
        ok_action = p["action"] == want_action
        ok_sym = (p.get("symbol") == want_sym) if want_sym else (p.get("symbol") in (None, want_sym))
        check(f"nlp: {text}", ok_action and ok_sym, f"-> {p}")

    print("== Ani hareket alarmi ==")
    from database import add_watch as db_add_watch
    from services import alerts as alert_mod
    db_add_watch(USER, "AAPL")
    big1 = alert_mod.check_big_moves(threshold_pct=0.0)
    check("big move tetiklendi", len(big1) >= 1 and big1[0]["symbol"] == "AAPL", f"{len(big1)} bildirim")
    big2 = alert_mod.check_big_moves(threshold_pct=0.0)
    check("gun icinde tekrar yok", len(big2) == 0, f"{len(big2)} bildirim")

    print("== PostgreSQL SQL hazirligi (canli DB olmadan) ==")
    import database as dbmod
    # placeholder donusumu + RETURNING id
    s = dbmod._pg_prepare("INSERT INTO alerts (user_id, symbol) VALUES (?, ?)")
    check("pg INSERT + RETURNING", s.endswith("RETURNING id") and "?" not in s and "%s" in s, s)
    s2 = dbmod._pg_prepare("UPDATE alerts SET active = 0 WHERE id = ? AND user_id = ?")
    check("pg UPDATE %s", "?" not in s2 and s2.count("%s") == 2 and "RETURNING" not in s2, s2)
    s3 = dbmod._pg_prepare("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT(user_id) DO NOTHING")
    check("pg INSERT user_id RETURNING", s3.endswith("RETURNING user_id"), s3)
    s4 = dbmod._pg_prepare("INSERT INTO budgets (user_id, salary) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET salary = excluded.salary")
    check("pg INSERT budgets RETURNING", s4.endswith("RETURNING user_id"), s4)
    # schema parcalama + AUTOINCREMENT -> SERIAL
    stmts = [x.strip() for x in dbmod._SCHEMA.split(";") if x.strip()]
    check("schema stmt sayisi (16 tablo + 4 indeks)", len(stmts) == 20, f"{len(stmts)} stmt")
    tables = [x for x in stmts if x.startswith("CREATE TABLE")]
    check("16 tablo", len(tables) == 16, f"{len(tables)} tablo")
    watch_stmt = next(x for x in stmts if "watchlist" in x and "CREATE TABLE" in x)
    pg_watch = watch_stmt.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    check("pg AUTOINCREMENT -> SERIAL", "SERIAL PRIMARY KEY" in pg_watch and "AUTOINCREMENT" not in pg_watch)
    check("pg schema '?' yok", all("?" not in x for x in stmts))

    print("== Nakit hesabi ==")
    from database import add_cash, get_cash, set_cash
    set_cash(USER, 20000)
    check("set_cash 20000", get_cash(USER) == 20000)
    add_cash(USER, -1500)
    check("add_cash -1500", get_cash(USER) == 18500)
    add_cash(USER, 50000)
    check("add_cash maas +50000", get_cash(USER) == 68500)

    print("== Dengeleme ==")
    from services import assistant as asst
    # Canta: 30k hisse (stocks), 10k kripto, 10k nakit; toplam 50k
    class FakePos:
        def __init__(self, sym, mv):
            self.symbol, self.market_value = sym, mv
    check("classify .IS -> stocks", asst.classify_symbol("THYAO.IS") == "stocks")
    check("classify BTC -> crypto", asst.classify_symbol("BTC-USD") == "crypto")
    check("classify GC=F -> gold", asst.classify_symbol("GC=F") == "gold")
    check("classify TRY=X -> cash", asst.classify_symbol("TRY=X") == "cash")

    plan = assistant.build_plan(50000, 25000, "dengeli", "acil_fon", 8)
    pos = [FakePos("THYAO.IS", 30000), FakePos("BTC-USD", 10000)]
    r = asst.rebalance(plan, pos, cash=10000)
    check("rebalance total 50000", abs(r["total"] - 50000) < 1, str(r["total"]))
    # dengeli hedef: stocks 50 (25000), gold 30 (15000), cash 20 (10000), crypto 0
    # mevcut: stocks 30000, crypto 10000, cash 10000
    # -> stocks asiri (30000 > 25000) SAT ~5000; crypto SAT ~10000; gold eksik AL ~15000 (nakit 10000 ile sinirli)
    sell_classes = {s[0] for s in r["sells"]}
    check("crypto satilmali", "crypto" in sell_classes, str(sell_classes))
    buy_classes = {b[0] for b in r["buys"]}
    check("gold alinmali", "gold" in buy_classes, str(buy_classes))
    total_buy = sum(b[3] for b in r["buys"])
    check("alimlar nakti asmaz", total_buy <= 10000 + 1, f"buy={total_buy}")
    check("rebalance_message", "Ne Alayım" in asst.rebalance_message(plan, pos, 10000))

    print("== Otomatik secici ==")
    from services import picker
    _orig_safe, _orig_risky = picker.SAFE_POOL, picker.RISKY_POOL
    picker.SAFE_POOL = ["THYAO.IS", "AAPL"]
    picker.RISKY_POOL = ["BTC-USD", "SOL-USD"]
    pres = picker.pick(plan, [], cash=5000)
    picker.SAFE_POOL, picker.RISKY_POOL = _orig_safe, _orig_risky
    check("picker cikti yapisi", "safe" in pres and "risky" in pres and "sells" in pres)
    check("picker profil bolunmesi", pres["safe_pct"] == 60 and pres["risky_pct"] == 40, f"{pres['safe_pct']}/{pres['risky_pct']}")
    check("picker mesaj", "Otomatik Seçimler" in picker.pick_message(pres))

    print("== Temel analiz / Backtest / Risk / Makro ==")
    from services import backtest as bt_mod, fundamentals as fund, macro as macro_mod, risk as risk_mod
    # Temel skor (canli ag olmadan, ornek veriyle)
    ff = {"pe": 8, "pb": 1.2, "roe": 0.18, "profit_margin": 0.15,
          "revenue_growth": 0.12, "debt_to_equity": 40, "dividend_yield": 0.03,
          "market_cap": 10, "currency": "TRY", "sector": "Sanayi"}
    fscore, flabel = fund.score_fundamentals(ff)
    check("temel skor", fscore >= 50, f"skor={fscore} {flabel}")
    check("temel metin", "F/K" in fund.fundamentals_text(ff))

    # Backtest (gercek veri, 1 yil)
    bt = bt_mod.backtest("AAPL", "1y")
    check("backtest AAPL", bt is not None and "strategy_return" in bt,
          f"getiri=%{bt['strategy_return']:.1f}" if bt else "YOK")
    check("backtest metin", "Backtest" in bt_mod.backtest_text(bt))

    # Risk analizi
    rp = risk_mod.analyze([FakePos("THYAO.IS", 40000), FakePos("BTC-USD", 10000)], cash=5000)
    check("risk analizi", rp["ok"] and rp["n_positions"] == 2)
    check("risk konsantrasyonu", rp["top_weight"] > 70, f"%{rp['top_weight']:.0f}")
    check("risk metin", "Risk Analizi" in risk_mod.risk_text(rp))

    # Makro panel
    mtext = macro_mod.dashboard()
    check("makro panel", "Makro" in mtext and "USD/TRY" in mtext)

    print("== Notlar ==")
    from database import add_note, get_notes
    add_note(USER, "THYAO.IS", "Test notu")
    notes = get_notes(USER, "THYAO.IS")
    check("not ekle", len(notes) == 1 and notes[0]["note"] == "Test notu")

    print("== Gelismis alarmlar ==")
    from services import advanced_alerts as aa_mod
    help_text = aa_mod.format_alert_help()
    check("alarm2 yardim", "RSI" in help_text and "MACD" in help_text)
    # Parametre dogrulama
    ok, _ = aa_mod.validate_alert_config("rsi", {"threshold": 30, "direction": "below"})
    check("rsi alarm dogrulama", ok)
    ok, _ = aa_mod.validate_alert_config("macd", {"direction": "cross_up"})
    check("macd alarm dogrulama", ok)
    ok, _ = aa_mod.validate_alert_config("bb", {"band": "upper", "direction": "above"})
    check("bb alarm dogrulama", ok)
    ok, _ = aa_mod.validate_alert_config("volume", {"multiplier": 2})
    check("hacim alarm dogrulama", ok)
    ok, _ = aa_mod.validate_alert_config("price", {"target": 100, "direction": "above"})
    check("fiyat alarm dogrulama", ok)

    print("== Performans ==")
    from services import performance as perf_mod
    attr_text = perf_mod.attribution_text(USER)
    check("performans atfi", "Performans Atfı" in attr_text)

    print("== Karsilastirma ==")
    from services import fundamentals as fund
    ff1 = {"pe": 10, "pb": 1.5, "roe": 0.20, "profit_margin": 0.15}
    ff2 = {"pe": 25, "pb": 3.0, "roe": 0.08, "profit_margin": 0.05}
    check("temel karsilastirma veri", fund.score_fundamentals(ff1)[0] > fund.score_fundamentals(ff2)[0])

    print("== Takvim ==")
    from services import calendar as cal_mod
    events = cal_mod.get_upcoming_events(None, 7)
    check("takvim bos", isinstance(events, list))

    print("== Inline query parse ==")
    from services import inline as inline_mod
    syms = inline_mod.parse_inline_query("THYAO AAPL BTC")
    check("inline parse", "THYAO.IS" in syms and "AAPL" in syms and "BTC-USD" in syms)

    print()
    if FAIL:
        print(f"SONUC: {len(FAIL)} HATA -> {FAIL}")
        raise SystemExit(1)
    print("SONUC: Tum testler gecti (OK)")


if __name__ == "__main__":
    main()
