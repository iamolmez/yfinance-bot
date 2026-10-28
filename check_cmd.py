with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()
if 'async def cmd_menu' in content:
    print('cmd_menu function found')
else:
    print('cmd_menu NOT found')
if 'CommandHandler("menu"' in content or "CommandHandler('menu'" in content:
    print('Handler registered')
else:
    print('Handler NOT registered - need to add')