with open('services/menu.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the incorrectly replaced closing brackets
# Change '),\n' back to '],\n' for dict value lists
content = content.replace('        ]),\n', '        ],\n')

# Fix the return statement - remove extra closing paren
content = content.replace(
    'return InlineKeyboardMarkup(buttons.get(context, [[InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")]]))',
    'return InlineKeyboardMarkup(buttons.get(context, [[InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")]]))'
)

with open('services/menu.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed menu.py')