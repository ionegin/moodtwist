# menu_config.py
MENUS = {
    'main': {
        'type': 'reply',
        'buttons': [
            {'text': '📊 Пройти опрос', 'row': 0},
            {'text': '✏️ РЕДАКТИРОВАТЬ', 'row': 1},
        ],
        'resize_keyboard': True,
        'one_time': False,
    },
    'edit': {
        'type': 'reply',
        'buttons': [
            {'text': '💤 Прибавить сон', 'row': 0},
            {'text': '💼 Прибавить продуктивность', 'row': 1},
            {'text': '🧘 Прибавить медитацию', 'row': 2},
            {'text': '🎭 Опрос настроения', 'row': 3},
            {'text': '💊 Модафинил / 🧘 Йога', 'row': 4},
            {'text': '📆 Запись в прошлом', 'row': 5},
            {'text': '🔙 Назад', 'row': 6},
        ],
        'resize_keyboard': True,
        'one_time': False,
    },
    'yesno_edit': {
        'type': 'inline',
        'buttons': [
            {'text': '💊 Модафинил', 'action': 'ynedit:modafinil'},
            {'text': '🧘 Йога', 'action': 'ynedit:yoga'},
            {'text': '❌ Отмена', 'action': 'ynedit:cancel'},
        ],
    },
}
