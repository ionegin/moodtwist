# handlers.py
"""
Обработчики команд бота.
Выделены в отдельный файл для удобства редактирования Opus/Claude.
"""
from aiogram import types
from aiogram.fsm.context import FSMContext
from menu import render_menu
from datetime import datetime, timedelta

async def handle_start(message: types.Message):
    """Команда /start - показать главное меню"""
    keyboard = render_menu('main')
    await message.answer(
        "🧠 *Borderliner System*\n\n"
        "Выбери действие:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def handle_menu(message: types.Message):
    """Открыть меню (пока просто главный экран)"""
    keyboard = render_menu('main')
    await message.answer("📝 Меню:", reply_markup=keyboard)


async def handle_edit_history(message: types.Message, state: FSMContext):
    """
    Редактирование истории.
    TODO: Полная реализация с Opus (ConversationHandler)
    """
    keyboard = render_menu('edit_date')
    await message.answer(
        "📅 Выбери день для редактирования:",
        reply_markup=keyboard
    )
    # Пока просто показываем кнопки
    # Полная state machine будет добавлена позже


async def handle_edit_date_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Обработка выбора даты.
    TODO: Полная реализация
    """
    action = callback.data.split(':')[1]
    
    if action == 'manual':
        await callback.message.answer("Введи дату в формате ДД.ММ.ГГ (например: 22.02.26)")
        # TODO: State для ожидания ввода даты
    elif action == 'cancel':
        keyboard = render_menu('main')
        await callback.message.answer("❌ Отменено", reply_markup=keyboard)
    else:
        # action = "-1", "-2" и т.д. (дни назад)
        days_ago = int(action)
        date = datetime.now() + timedelta(days=days_ago)
        await callback.message.answer(f"📅 Выбрана дата: {date.strftime('%d.%m.%Y')}")
        # TODO: Показать список метрик для редактирования
    
    await callback.answer()
