# menu.py
"""
Генерация клавиатур из menu_config.py
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from menu_config import MENUS

def render_menu(menu_name: str):
    """
    Рендерит меню по имени из menu_config.
    Возвращает ReplyKeyboardMarkup или InlineKeyboardMarkup.
    """
    config = MENUS.get(menu_name)
    if not config:
        raise ValueError(f"Меню '{menu_name}' не найдено в menu_config.py")
    
    if config['type'] == 'reply':
        return _render_reply_keyboard(config)
    elif config['type'] == 'inline':
        return _render_inline_keyboard(config)
    else:
        raise ValueError(f"Неизвестный тип меню: {config['type']}")


def _render_reply_keyboard(config):
    """ReplyKeyboard (постоянная клавиатура)"""
    # Группируем кнопки по row
    rows = {}
    for btn in config['buttons']:
        row_num = btn.get('row', 0)
        if row_num not in rows:
            rows[row_num] = []
        rows[row_num].append(KeyboardButton(text=btn['text']))
    
    # Собираем в список списков
    keyboard = [rows[i] for i in sorted(rows.keys())]
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=config.get('resize_keyboard', True),
        one_time_keyboard=config.get('one_time', False)
    )


def _render_inline_keyboard(config):
    """InlineKeyboard (под сообщением)"""
    buttons = []
    for btn in config['buttons']:
        buttons.append([InlineKeyboardButton(
            text=btn['text'],
            callback_data=btn['action']
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
