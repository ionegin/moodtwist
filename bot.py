import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime, timedelta

from config import BOT_TOKEN, WEBHOOK_BASE_URL
import survey_provider
from question_types import val_to_ru, opposite_val, opposite_ru
from question_types import render as render_question
from question_types import validate as validate_answer
from storage.sheets import GoogleSheetsStorage
from menu import render_menu, MOOD_SURVEY_LABEL
from handlers import handle_start
from services.transcription import transcribe_voice
from services.notifications import setup_notifications_v2
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()
storage = GoogleSheetsStorage()

# Динамические кнопки меню «Редактировать» (заполняются после load_schema)
QUICK_ADD_BUTTONS = {}
YESNO_GROUP_LABELS = set()


def _build_dynamic_buttons():
    """Собирает label->key соответствия quick-add и лейблы yes_no-группы из схемы."""
    QUICK_ADD_BUTTONS.clear()
    YESNO_GROUP_LABELS.clear()
    for key in survey_provider.list_summable():
        QUICK_ADD_BUTTONS[survey_provider.get_button_label(key)] = key
    group_label = survey_provider.get_yesno_group_label()
    if group_label:
        YESNO_GROUP_LABELS.add(group_label)

scheduler = None
scheduler_initialized = False


def get_scheduler():
    global scheduler, scheduler_initialized
    if scheduler is None:
        scheduler = AsyncIOScheduler()
    if not scheduler_initialized:
        setup_notifications_v2(scheduler, bot, get_users)
        scheduler_initialized = True
    return scheduler


def ensure_scheduler_started():
    scheduler_instance = get_scheduler()
    if not scheduler_instance.running:
        scheduler_instance.start()
    return scheduler_instance


async def run_bot():
    if not BOT_TOKEN or bot is None:
        raise RuntimeError("TELEGRAM_TOKEN is not configured")

    await survey_provider.load_schema()
    _build_dynamic_buttons()

    scheduler_instance = ensure_scheduler_started()
    try:
        me = await bot.get_me()
        logging.info("Bot connected to Telegram as @%s", me.username)
        await dp.start_polling(bot, handle_signals=False)
    finally:
        if scheduler_instance.running:
            scheduler_instance.shutdown(wait=False)

class Survey(StatesGroup):
    waiting_for_metrics = State()

class YesNoEdit(StatesGroup):
    waiting_for_value = State()

class QuickAdd(StatesGroup):
    waiting_for_value = State()

class PastEdit(StatesGroup):
    waiting_for_date = State()

class SurveyLink(StatesGroup):
    waiting_for_url = State()

USERS_FILE = "users.txt"
def get_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return {int(x.strip()) for x in f if x.strip()}
    return set()

def save_user(uid):
    users = get_users()
    if uid not in users:
        with open(USERS_FILE, "a") as f:
            f.write(f"{uid}\n")

def get_logical_date(dt: datetime):
    local = dt + timedelta(hours=2)  # UTC+2, сутки считаются с 06:00
    if local.hour < 6:
        return str((local - timedelta(days=1)).strftime("%Y-%m-%d"))
    return str(local.strftime("%Y-%m-%d"))

async def ask_next_metric(chat_id: int, state: FSMContext, idx: int):
    data = await state.get_data()
    metrics_to_ask = data["metrics_to_ask"]
    if idx >= len(metrics_to_ask):
        return False

    key = metrics_to_ask[idx]
    cfg = survey_provider.get_metric_config(key)
    existing = data.get("existing", {})
    existing_val = existing.get(key)

    # Пропуск: вычисляемые метрики (computed_from) и типы «один раз в день»,
    # у которых ответ за день уже дан (time/yes_no).
    while (survey_provider.is_computed(key)
           or (cfg.get("ask_once_per_day") and existing_val is not None)):
        idx += 1
        await state.update_data(current_idx=idx)
        if idx >= len(metrics_to_ask):
            return False
        key = metrics_to_ask[idx]
        cfg = survey_provider.get_metric_config(key)
        existing_val = existing.get(key)

    text, markup = render_question(
        cfg.get("type"), key, cfg.get("question"), existing_val, cfg
    )
    await bot.send_message(chat_id, text, reply_markup=markup)
    return True
# ─── СТАРТ ───────────────────────────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    save_user(message.chat.id)
    await state.clear()
    await handle_start(message)

# ─── ОПРОС ───────────────────────────────────────────────────────────────────

@dp.message(Command("daily"))
async def start_daily(message: types.Message, state: FSMContext):
    await _launch_survey(message, state)

@dp.message(F.text.in_({"📊 ПРОЙТИ ОПРОС", "📊 Пройти опрос"}))
async def daily_button(message: types.Message, state: FSMContext):
    await _launch_survey(message, state)

async def _launch_survey(message: types.Message, state: FSMContext, date_override: str = None):
    save_user(message.chat.id)
    if date_override:
        l_date = date_override
        is_past_edit = True
    else:
        l_date = get_logical_date(message.date)
        is_past_edit = False
        
    metrics = survey_provider.get_survey_metrics("daily")
    if not metrics:
        await message.answer("😴 Опрос временно недоступен. Попробуй позже.")
        return

    existing = storage.get_day_data(message.chat.id, l_date)
    await state.update_data(
        metrics_to_ask=list(metrics),
        answers={},
        current_idx=0,
        logical_date=l_date,
        existing=existing,
        is_past_edit=is_past_edit,
    )
    await state.set_state(Survey.waiting_for_metrics)
    await ask_next_metric(message.chat.id, state, 0)

@dp.message(Survey.waiting_for_metrics, F.text)
async def handle_metrics_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    idx, answers = data["current_idx"], data["answers"]
    key = data["metrics_to_ask"][idx]
    cfg = survey_provider.get_metric_config(key)

    value, error = validate_answer(
        cfg.get("type"), key, message.text, cfg, data.get("existing", {})
    )
    if error:
        await message.answer(error)
        return
    if value is not None:
        answers[key] = value

    idx += 1
    await state.update_data(answers=answers, current_idx=idx)
    if not await ask_next_metric(message.chat.id, state, idx):
        await finish_survey(message, state)

@dp.callback_query(Survey.waiting_for_metrics, F.data.startswith("m:"))
async def handle_metrics_callback(callback: CallbackQuery, state: FSMContext):
    _, key, value = callback.data.split(":")
    data = await state.get_data()
    answers, idx = data["answers"], data["current_idx"]

    answers[key] = None if value in ("keep", "skip") else value

    idx += 1
    await state.update_data(answers=answers, current_idx=idx)
    await callback.answer()
    if not await ask_next_metric(callback.message.chat.id, state, idx):
        await finish_survey(callback.message, state)

async def finish_survey(message: types.Message, state: FSMContext):
    data = await state.get_data()
    logical_day = data.get("logical_date")
    answers = data["answers"]

    # Вычисляем метрики, помеченные computed_from (например, sleep_hours из sleep_time/wake_time)
    for key in data.get("metrics_to_ask", []):
        if survey_provider.is_computed(key):
            computed = survey_provider.compute_metric(key, answers)
            if computed is not None:
                answers[key] = str(computed)
                print(f"[SURVEY] computed {key}={computed}")

    local_now = message.date + timedelta(hours=2)
    is_past_edit = data.get("is_past_edit", False)
    if is_past_edit:
        created_at = f"{logical_day} 12:01"
    else:
        created_at = str(local_now.strftime("%Y-%m-%d %H:%M"))

    # Заметки (type=note) пишем только в лист Notes; из строки дня их убираем
    final_row = {"Date": logical_day, "created_at": created_at}
    notes = {}
    for key in list(answers.keys()):
        if survey_provider.get_type(key) == "note":
            note_text = answers[key]
            if note_text and str(note_text).strip():
                notes[key] = str(note_text).strip()
        else:
            final_row[key] = answers[key]

    if "ai_score" not in final_row:
        final_row["ai_score"] = ""

    print(f"[SURVEY] saving {len(final_row)} fields for date={logical_day}")
    storage.save_daily(message.chat.id, final_row)

    for note_text in notes.values():
        storage.save_note(
            user_id=message.chat.id,
            text=note_text,
            is_voice=False,
            telegram_ts=message.date if not is_past_edit else None,
            source="mood_note",
            created_at_override=created_at,
        )

    await message.answer(f"✅ Данные сохранены за {logical_day}!", reply_markup=render_menu('main'))
    await state.clear()

# ─── МЕНЮ РЕДАКТИРОВАТЬ ───────────────────────────────────────────────────────

@dp.message(F.text == "✏️ РЕДАКТИРОВАТЬ")
async def edit_menu(message: types.Message):
    save_user(message.chat.id)
    await message.answer("✏️ Что редактируем?", reply_markup=render_menu('edit'))

@dp.message(F.text == "🔙 Назад")
async def back_to_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню", reply_markup=render_menu('main'))

# ─── ССЫЛКА НА ОПРОС ──────────────────────────────────────────────────────────

@dp.message(F.text == "🔗 Указать ссылку на вопросы")
async def btn_set_survey_link(message: types.Message, state: FSMContext):
    await state.set_state(SurveyLink.waiting_for_url)
    await message.answer(
        "🔗 Пришли публичную ссылку на JSON опроса (http/https).\n"
        "Она запишется в PASTE_SURVEY_HERE.json, inline-версия останется как запас."
    )

@dp.message(SurveyLink.waiting_for_url, F.text)
async def handle_set_survey_link(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("⚠️ Это не похоже на ссылку. Нужен http(s) URL.")
        return
    try:
        survey_provider.set_survey_url(url)
    except Exception as e:
        logging.error("[SURVEY] failed to save url: %s", e)
        await message.answer("❌ Не удалось сохранить ссылку в файл.")
        await state.clear()
        return
    await message.answer("🔗 Ссылка сохранена. Проверяю опрос...")
    try:
        await survey_provider.load_schema()
    except Exception as e:
        logging.error("[SURVEY] reload failed: %s", e)
    metrics = survey_provider.list_metrics()
    if metrics:
        await message.answer(f"✅ Опрос обновлён ({len(metrics)} метрик):\n{url}")
    else:
        await message.answer("⚠️ По ссылке не удалось загрузить валидный опрос. Используется кэш/fallback.")
    await state.clear()

# ─── БЫСТРОЕ ПРИБАВЛЕНИЕ ──────────────────────────────────────────────────────

async def _start_quick_add(message: types.Message, state: FSMContext, metric_key: str):
    save_user(message.chat.id)
    l_date = get_logical_date(message.date)
    existing = storage.get_day_data(message.chat.id, l_date)
    current_val = existing.get(metric_key)
    cfg = survey_provider.get_metric_config(metric_key)
    unit = cfg.get("unit", "")

    if current_val is not None:
        try:
            display = round(float(str(current_val).replace(',', '.')), 1)
        except (ValueError, TypeError):
            display = current_val
    else:
        display = 0

    await state.update_data(metric_key=metric_key)
    await state.set_state(QuickAdd.waiting_for_value)
    await message.answer(f"Сейчас: {display} {unit}. Сколько прибавить?")

# Кнопки quick-add и yes_no-группы генерируются из схемы (label->key),
# поэтому обработчики динамические: F.text.in_ с mutable-контейнером,
# который заполняется в _build_dynamic_buttons() после load_schema().
@dp.message(F.text.in_(QUICK_ADD_BUTTONS))
async def handle_quick_add_button(message: types.Message, state: FSMContext):
    key = QUICK_ADD_BUTTONS.get(message.text.strip())
    if key:
        await _start_quick_add(message, state, key)

@dp.message(F.text == MOOD_SURVEY_LABEL)
async def btn_mood_survey(message: types.Message, state: FSMContext):
    save_user(message.chat.id)
    l_date = get_logical_date(message.date)
    existing = storage.get_day_data(message.chat.id, l_date)
    mood_metrics = survey_provider.get_survey_metrics("mood")
    if not mood_metrics:
        await message.answer("😴 Опрос настроения временно недоступен.")
        return
    await state.update_data(
        metrics_to_ask=list(mood_metrics),
        answers={},
        current_idx=0,
        logical_date=l_date,
        existing=existing,
    )
    await state.set_state(Survey.waiting_for_metrics)
    await ask_next_metric(message.chat.id, state, 0)

@dp.message(QuickAdd.waiting_for_value, F.text)
async def handle_quick_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    key = data["metric_key"]
    try:
        val = str(float(message.text.strip().replace(',', '.')))
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи число.")
        return

    local_now = message.date + timedelta(hours=2)
    final_row = {
        "Date": get_logical_date(message.date),
        "created_at": str(local_now.strftime("%Y-%m-%d %H:%M")),
        key: val
    }
    storage.save_daily(message.chat.id, final_row)
    await message.answer("✅ Данные добавлены!", reply_markup=render_menu('edit'))
    await state.clear()

# ─── РЕДАКТИРОВАНИЕ YES-NO ───────────────────────────────────────────────────

@dp.message(F.text.in_(YESNO_GROUP_LABELS))
async def yesno_edit_button(message: types.Message):
    await message.answer("✏️ Что редактируем?", reply_markup=render_menu('yesno_edit'))

@dp.callback_query(F.data.startswith("ynedit:"))
async def handle_yesno_edit_select(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cancel":
        await callback.message.edit_text("❌ Отменено")
        await bot.send_message(callback.message.chat.id, "Редактировать", reply_markup=render_menu('edit'))
        return

    metric_key = action
    logical_day = get_logical_date(callback.message.date)
    current_val = storage.check_today_metric(callback.message.chat.id, metric_key, logical_day)

    await state.update_data(metric_key=metric_key, logical_day=logical_day)
    await state.set_state(YesNoEdit.waiting_for_value)

    question = survey_provider.get_metric_config(metric_key).get("question")

    if current_val is not None:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"✅ Оставить ({val_to_ru(current_val)})", callback_data=f"yn:{opposite_val(current_val)}:keep"),
            InlineKeyboardButton(text=f"🔄 → {opposite_ru(current_val)}", callback_data=f"yn:{opposite_val(current_val)}:set"),
        ]])
        await callback.message.edit_text(f"✏️ {question}\n(Сейчас: {val_to_ru(current_val)})", reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Да", callback_data="yn:yes:set"),
            InlineKeyboardButton(text="Нет", callback_data="yn:no:set"),
        ]])
        await callback.message.edit_text(f"✏️ {question}\n(Записей нет)", reply_markup=kb)

@dp.callback_query(YesNoEdit.waiting_for_value, F.data.startswith("yn:"))
async def handle_yesno_edit_val(callback: CallbackQuery, state: FSMContext):
    _, value, action = callback.data.split(":")
    data = await state.get_data()
    metric_key = data["metric_key"]
    logical_day = data["logical_day"]

    if action == "keep":
        await callback.message.edit_text("✅ Без изменений.")
    else:
        storage.update_first_row_yesno(callback.message.chat.id, logical_day, metric_key, value)
        question = survey_provider.get_metric_config(metric_key).get("question")
        await callback.message.edit_text(f"✅ {question} → {val_to_ru(value)}")

    await bot.send_message(callback.message.chat.id, "Редактировать", reply_markup=render_menu('edit'))
    await state.clear()
    await callback.answer()

# ─── ГОЛОСОВЫЕ И ТЕКСТОВЫЕ ЗАМЕТКИ ──────────────────────────────────────────

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    print(f"[VOICE] received from {message.chat.id}")
    path = f"voice_{message.voice.file_id}.ogg"
    try:
        file = await bot.get_file(message.voice.file_id)
        await bot.download_file(file.file_path, path)
        text = await transcribe_voice(path)
        print(f"[VOICE] transcribed: {text}")
        storage.save_note(
            user_id=message.chat.id,
            text=text,
            is_voice=True,
            duration=message.voice.duration,
            telegram_ts=message.date,
            uploaded_at=datetime.now(),
        )
        await message.answer(f"🎙️ Записал заметку:\n_{text}_", parse_mode="Markdown")
    except Exception as e:
        print(f"[VOICE] ERROR: {e}")
        import traceback
        traceback.print_exc()
        await message.answer("❌ Не удалось расшифровать голосовое")
    finally:
        if os.path.exists(path):
            os.remove(path)

@dp.message(F.text)
async def handle_text_note(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        text = message.text
        print(f"[NOTE] saving: {text[:50]}")
        storage.save_note(
            user_id=message.chat.id,
            text=text,
            is_voice=False,
            telegram_ts=message.date,
            uploaded_at=datetime.now(),
        )
        await message.answer("📝 Заметка сохранена.")

# ─── ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ──────────────────────────────────────────────

@dp.message(F.text == "📆 Запись в прошлом")
async def btn_past_record(message: types.Message, state: FSMContext):
    save_user(message.chat.id)
    await state.set_state(PastEdit.waiting_for_date)
    await message.answer("Выбери дату:", reply_markup=await SimpleCalendar().start_calendar())

@dp.callback_query(SimpleCalendarCallback.filter(), PastEdit.waiting_for_date)
async def process_simple_calendar(callback_query: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if selected:
        target_date = date.strftime("%Y-%m-%d")
        if date.date() > datetime.now().date():
            await callback_query.message.answer("⚠️ Нельзя выбирать дату в будущем!")
            return
        
        await state.update_data(target_date=target_date)
        existing = storage.get_day_data(callback_query.message.chat.id, target_date)
        
        text = f"📅 Данные за {target_date}:\n\n"
        if existing:
            for k, v in existing.items():
                if k not in ["Date", "created_at"]:
                    text += f"• {k}: {v}\n"
        else:
            text += "Записей пока нет."
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔄 Отредактировать / Заполнить", callback_data=f"past_edit:{target_date}"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="past_cancel"),
        ]])
        await callback_query.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("past_edit:"))
async def handle_past_edit_start(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[1]
    await _launch_survey(callback.message, state, date_override=date_str)
    await callback.answer()

@dp.callback_query(F.data == "past_cancel")
async def handle_past_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await bot.send_message(callback.message.chat.id, "Редактировать", reply_markup=render_menu('edit'))
    await callback.answer()

if __name__ == "__main__":
    asyncio.run(run_bot())
