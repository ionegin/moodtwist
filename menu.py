# menu.py
"""
Генерация клавиатур: статичные из menu_config.py + динамические
('edit', 'yesno_edit') из каталога survey_provider.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from menu_config import MENUS
from survey_provider import list_summable, list_yes_no, get_button_label, get_yesno_group_label

MOOD_SURVEY_LABEL = "🎭 Опрос настроения"

def render_menu(menu_name: str):
    """Рендерит меню по имени. 'edit'/'yesno_edit' собираются динамически из схемы."""
    if menu_name == "edit":
        return _render_edit_menu()
    if menu_name == "yesno_edit":
        return _render_yesno_edit_menu()
    config = MENUS.get(menu_name)
    if not config:
        raise ValueError(f"Меню '{menu_name}' не найдено в menu_config.py")

    if config['type'] == 'reply':
        return _render_reply_keyboard(config)
    elif config['type'] == 'inline':
        return _render_inline_keyboard(config)
    else:
        raise ValueError(f"Неизвестный тип меню: {config['type']}")


def _render_edit_menu():
    """Reply-клавиатура: quick-add числа, опрос настроения, yes_no-группа, навигация."""
    buttons = []
    for key in list_summable():
        buttons.append([KeyboardButton(text=get_button_label(key))])
    buttons.append([KeyboardButton(text=MOOD_SURVEY_LABEL)])
    group_label = get_yesno_group_label()
    if group_label:
        buttons.append([KeyboardButton(text=group_label)])
    buttons.append([KeyboardButton(text="📆 Запись в прошлом")])
    buttons.append([KeyboardButton(text="🔙 Назад")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def _render_yesno_edit_menu():
    """Inline-подменю для редактирования yes_no-метрик."""
    buttons = []
    for key in list_yes_no():
        buttons.append([InlineKeyboardButton(text=get_button_label(key), callback_data=f"ynedit:{key}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="ynedit:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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

