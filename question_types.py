# question_types.py
"""
Реестр ВИДОВ вопросов. Логика каждого типа фиксирована в коде:
рендер вопроса, кнопки, валидация ввода и агрегация значений за день.
Конкретные вопросы/метрики приходят из внешнего JSON (survey_provider).
"""
import re

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def val_to_ru(val):
    if val == "yes":
        return "Да"
    if val == "no":
        return "Нет"
    return val


def opposite_val(val):
    return "no" if val == "yes" else "yes"


def opposite_ru(val):
    return "Нет" if val == "yes" else "Да"


def _cb(key, value):
    return f"m:{key}:{value}"


# ─── scale (1–10) ─────────────────────────────────────────────────────────────

def _scale_render(key, question, existing_val, cfg):
    return f"📊 {question} ({cfg.get('min', 1)}–{cfg.get('max', 10)})", None


def _scale_validate(key, raw, cfg, existing=None):
    try:
        val = float(raw.strip().replace(",", "."))
    except ValueError:
        return None, f"⚠️ Введи число от {cfg.get('min', 1)} до {cfg.get('max', 10)}."
    if val < cfg.get("min", 1) or val > cfg.get("max", 10):
        return None, f"⚠️ Введи число от {cfg.get('min', 1)} до {cfg.get('max', 10)}."
    return str(int(val)) if val == int(val) else str(val), None


def _mean(values):
    nums = []
    for v in values:
        try:
            nums.append(float(str(v).replace(",", ".")))
        except (ValueError, TypeError):
            continue
    if not nums:
        return None
    return round(sum(nums) / len(nums), 1)


# ─── number (суммируемое свободное число) ────────────────────────────────────

def _number_render(key, question, existing_val, cfg):
    if existing_val is not None:
        try:
            val_display = round(float(existing_val), 1)
        except (ValueError, TypeError):
            val_display = existing_val
    else:
        val_display = 0
    unit = cfg.get("unit", "")
    text = f"{question}\n(Сейчас: {val_display} {unit}. Сколько ПРИБАВИТЬ?)"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"✅ Оставить ({val_display})", callback_data=_cb(key, "keep")),
    ]])
    return f"📊 {text}", kb


def _number_validate(key, raw, cfg, existing=None):
    try:
        val = float(raw.strip().replace(",", "."))
    except ValueError:
        return None, f"⚠️ Введи число от {cfg.get('min', 1)} до {cfg.get('max', '∞')}."
    if val < cfg.get("min", 1):
        return None, f"⚠️ Введи число от {cfg.get('min', 1)} до {cfg.get('max', '∞')}."
    if val > cfg.get("max", float("inf")):
        return None, f"⚠️ Введи число от {cfg.get('min', 1)} до {cfg.get('max')}."
    current_total = 0.0
    if existing:
        cur = existing.get(key)
        if cur is not None:
            try:
                current_total = float(str(cur).replace(",", "."))
            except (ValueError, TypeError):
                current_total = 0.0
    if current_total + val < 0:
        return None, f"⚠️ Итоговое значение не может быть меньше 0 (сейчас {current_total})."
    return str(val), None


def _sum_values(values):
    total = 0.0
    for v in values:
        try:
            total += float(str(v).replace(",", "."))
        except (ValueError, TypeError):
            continue
    return total


# ─── yes_no ───────────────────────────────────────────────────────────────────

def _yesno_render(key, question, existing_val, cfg):
    if existing_val is not None:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"✅ Оставить ({val_to_ru(existing_val)})", callback_data=_cb(key, "keep")),
            InlineKeyboardButton(text=f"🔄 → {opposite_ru(existing_val)}", callback_data=_cb(key, opposite_val(existing_val))),
        ]])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Да", callback_data=_cb(key, "yes")),
            InlineKeyboardButton(text="Нет", callback_data=_cb(key, "no")),
        ]])
    return f"📊 {question}", kb


def _yesno_validate(key, raw, cfg, existing=None):
    return None, "⚠️ Используй кнопки для ответа."


# ─── time (ЧЧ:ММ) ─────────────────────────────────────────────────────────────

def _time_render(key, question, existing_val, cfg):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data=_cb(key, "skip")),
    ]])
    return f"📊 {question} (формат ЧЧ:ММ)", kb


def _time_validate(key, raw, cfg, existing=None):
    val_str = raw.strip().replace(".", ":").replace(" ", ":")
    if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", val_str):
        return None, "⚠️ Введи время в формате ЧЧ:ММ (например, 23:30 или 08:00)."
    return val_str, None


# ─── note (свободный ответ) ───────────────────────────────────────────────────

def _note_render(key, question, existing_val, cfg):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Пропустить", callback_data=_cb(key, "skip")),
    ]])
    return f"📊 {question}", kb


def _note_validate(key, raw, cfg, existing=None):
    return raw.strip(), None


# ─── word (ответ одним словом; на будущее) ────────────────────────────────────

def _word_render(key, question, existing_val, cfg):
    return f"📊 {question} (одним словом)", None


def _word_validate(key, raw, cfg, existing=None):
    text = raw.strip()
    if not text or len(text.split()) > 1:
        return None, "⚠️ Ответ одним словом."
    return text, None


def _last_value(values):
    for v in reversed(values):
        if v is not None and str(v).strip():
            return v
    return None


# ─── Реестр типов ─────────────────────────────────────────────────────────────

QUESTION_TYPES = {
    "scale": {
        "min": 1,
        "max": 10,
        "ask_once_per_day": False,
        "render": _scale_render,
        "validate": _scale_validate,
        "aggregate": _mean,
    },
    "number": {
        "min": 1,
        "max": 10000,
        "unit": "",
        "ask_once_per_day": False,
        "render": _number_render,
        "validate": _number_validate,
        "aggregate": _sum_values,
    },
    "yes_no": {
        "ask_once_per_day": True,
        "render": _yesno_render,
        "validate": _yesno_validate,
        "aggregate": _last_value,
    },
    "time": {
        "ask_once_per_day": True,
        "render": _time_render,
        "validate": _time_validate,
        "aggregate": _last_value,
    },
    "note": {
        "ask_once_per_day": False,
        "render": _note_render,
        "validate": _note_validate,
        "aggregate": lambda values: None,
    },
    "word": {
        "ask_once_per_day": False,
        "render": _word_render,
        "validate": _word_validate,
        "aggregate": lambda values: None,
    },
}


def render(type_name, key, question, existing_val, cfg):
    """Возвращает (text, InlineKeyboardMarkup|None)."""
    entry = QUESTION_TYPES.get(type_name)
    if not entry:
        return f"📊 {question}", None
    return entry["render"](key, question, existing_val, cfg)


def validate(type_name, key, raw, cfg, existing=None):
    """Возвращает (value|None, error_text|None)."""
    entry = QUESTION_TYPES.get(type_name)
    if not entry:
        return raw.strip(), None
    return entry["validate"](key, raw, cfg, existing)


def aggregate(type_name, values):
    """Агрегирует список значений за день по логике типа."""
    entry = QUESTION_TYPES.get(type_name)
    if not entry or not values:
        return None
    return entry["aggregate"](values)

