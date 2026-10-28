with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''    await update.message.reply_text(
        "?? <b>Asistan Menusu</b>\\n\\nSana nasıl yardımcı olayım?", reply_markup=kb
    )


@restricted
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):'''

new = '''    await update.message.reply_text(
        "🤖 <b>Asistan Menusu</b>\\n\\nSana nasıl yardımcı olayım?", reply_markup=kb
    )


@restricted
async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ana menu - butonlarla tum islemler."""
    user = update.effective_user
    cash = await to_thread(get_cash, user.id)
    pf = await to_thread(portfolio.get_portfolio, user.id)
    invested = sum(p.market_value for p in pf["positions"])
    total = cash + invested
    positions = len(pf["positions"])
    
    plan_row = get_user_plan(user.id)
    risk_score = 5
    risk_level = "Dengeli"
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        risk_map = {"sakin": (3, "Koruma"), "dengeli": (5, "Dengeli"), "atilgan": (8, "Buyume")}
        risk_score, risk_level = risk_map.get(plan["risk"], (5, "Dengeli"))
    
    invest_progress = 0
    emergency_progress = 0
    if plan_row:
        plan = assistant.plan_from_json(plan_row["plan"])
        rep = budget.get_month_report(user.id)
        if plan["invest_share"]:
            invest_progress = min(100, rep["invested"] / plan["invest_share"] * 100)
        emergency_saved = plan_row["emergency_saved"] or 0
        if plan["emergency_target"]:
            emergency_progress = min(100, emergency_saved / plan["emergency_target"] * 100)
    
    # Use the menu system
    await update.message.reply_text(
        "🏠 <b>Ana Menu</b>\\nHangi islemi yapmak istiyorsun?",
        reply_markup=menu.main_menu()
    )


@restricted
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):'''

if old in content:
    content = content.replace(old, new)
    with open('bot/handlers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Added cmd_menu')
else:
    print('Pattern not found exactly')