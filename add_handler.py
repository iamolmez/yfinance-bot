with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'app.add_handler(CommandHandler("asistan", cmd_assistant))'
new = '''app.add_handler(CommandHandler("asistan", cmd_assistant))
    app.add_handler(CommandHandler("menu", cmd_menu))'''

if old in content:
    content = content.replace(old, new)
    with open('bot/handlers.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Added handler')
else:
    print('Pattern not found')

with open('bot/handlers.py', 'w', encoding='utf-8') as f:
    f.write(content)