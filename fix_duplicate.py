with open('bot/handlers.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the duplicated async def send_quote
content = content.replace(
    'async def send_quoteasync def send_quote(update: Update, arg: str) -> bool:',
    'async def send_quote(update: Update, arg: str) -> bool:'
)

with open('bot/handlers.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed duplicated send_quote')