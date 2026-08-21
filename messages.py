# messages.py
"""
Тексты сообщений бота.
Функции возвращают текст. Позже можно заменить на LLM API.
"""

def get_morning_message(user_id: int, yesterday_data: dict = None):
    """
    Утреннее напоминание.
    
    Args:
        user_id: ID пользователя
        yesterday_data: Данные за вчера (для персонализации)
    
    Returns:
        str: Текст сообщения
    
    TODO: Заменить на LLM API (Gemini/Claude)
    """
    # Сейчас: статический текст
    return "☀️ Доброе утро! Как спалось?"
    
    # Потом (раскомментить и добавить API):
    # if yesterday_data and yesterday_data.get('anxiety', 0) > 7:
    #     return gemini_api.generate(f"Дай совет, вчера тревога была {yesterday_data['anxiety']}")
    # return "☀️ Доброе утро! Как спалось?"


def get_evening_message(user_id: int):
    """Вечернее напоминание"""
    return "🌙 Время вечернего опроса! Нажми /daily"


def get_custom_reminder(user_id: int, reminder_type: str):
    """
    Кастомные напоминания.
    
    Args:
        reminder_type: Тип напоминания из config.REMINDERS
    """
    messages = {
        'morning': get_morning_message(user_id),
        'evening': get_evening_message(user_id),
        'afternoon': '☕ Как прошла первая половина дня?',
    }
    return messages.get(reminder_type, '🔔 Напоминание')
