from datetime import time
import logging

# Список пуш-уведомлений. 
# Закомментируйте строку, если хотите отключить конкретный пуш.
PUSH_NOTIFICATIONS = [
    {"time": time(9, 0), "text": "☀️ Доброе утро! Пора заполнить дневник, расскажи о своем самочувствии. /daily"},
    {"time": time(14, 0), "text": "🕒 Добрый день! Не забудь отметить свои показатели в дневнике. /daily"},
    {"time": time(20, 0), "text": "🌙 Добрый вечер! Время подвести итоги дня. /daily"},
]

async def _send_push(bot, chat_id, text):
    try:
        from menu import render_menu
        await bot.send_message(chat_id, text, reply_markup=render_menu('main'))
    except Exception as e:
        logging.error(f"Failed to send push to {chat_id}: {e}")

def setup_notifications(scheduler, bot, get_users):
    """Настраивает планировщик задач для отправки пушей."""
    for push in PUSH_NOTIFICATIONS:
        t = push['time']
        text = push['text']
        # Используем cron для ежедневной отправки в указанное время
        scheduler.add_job(
            _send_push, 
            'cron', 
            hour=t.hour, 
            minute=t.minute, 
            args=[bot, None, text] # chat_id будет передан внутри враппера
        )
        logging.info(f"Scheduled push at {t.hour:02d}:{t.minute:02d}")

# Переопределенный метод для массовой рассылки
async def mass_send_push(bot, get_users, text):
    for uid in get_users():
        await _send_push(bot, uid, text)

# Обновляем setup_notifications чтобы использовать mass_send_push
def setup_notifications_v2(scheduler, bot, get_users):
    """Настраивает планировщик задач для отправки пушей (версия с массовой рассылкой)."""
    for push in PUSH_NOTIFICATIONS:
        t = push['time']
        text = push['text']
        scheduler.add_job(
            mass_send_push, 
            'cron', 
            hour=t.hour, 
            minute=t.minute, 
            args=[bot, get_users, text]
        )
        logging.info(f"Scheduled push for everyone at {t.hour:02d}:{t.minute:02d}")
