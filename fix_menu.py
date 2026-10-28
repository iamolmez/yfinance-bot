with open('services/menu.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix InlineKeyboardMarkup closing parentheses
# Fix line 143: '    ]\n' -> '    ])\n' (first occurrence after subscription_detected_menu)
content = content.replace('    ]\n', '    ])\n', 1)

# Fix line 153: '        ],\n' -> '        ]),\n' (first occurrence in proactive_push_buttons)
content = content.replace('        ],\n', '        ]),\n', 1)

# Fix line 157 (second occurrence): '        ],\n' -> '        ]),\n'
content = content.replace('        ],\n', '        ]),\n', 1)

# Fix line 157 (second occurrence): '        ],\n' -> '        ]),\n'
content = content.replace('        ],\n', '        ]),\n', 1)

# Fix line 162: '        ],\n' -> '        ]),\n'
content = content.replace('        ],\n', '        ]),\n', 1)

# Fix line 166: '        ],\n' -> '        ]),\n'
content = content.replace('        ],\n', '        ]),\n', 1)

# Fix line 169: fix extra closing paren
content = content.replace(
    'return InlineKeyboardMarkup(buttons.get(context, [[InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")]]))',
    'return InlineKeyboardMarkup(buttons.get(context, [[InlineKeyboardButton("[GERI] Ana Menu", callback_data="menu:main")]]))'
)

with open('services/menu.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed menu.py')