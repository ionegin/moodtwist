# metrics.py

# Шаблоны измерений
MEASUREMENT_TYPES = {
    "hours": {
        "format": "number",
        "min": 0,
        "max": 24,
        "is_summable": True
    },
    "minutes": {
        "format": "number",
        "min": 0,
        "max": 999,
        "is_summable": True
    },
    "scale_10": {
        "format": "number",
        "min": 0,
        "max": 10,
    },
    "yes_no": {
        "format": "yes_no",
    },
    "note": {
        "format": "text",
        "optional": True,
    },
    "count": {
        "format": "number",
        "min": 0,
        "max": 20,
        "is_summable": True
    },
    "time": {
        "format": "time", # Changed from "text"
        "placeholder": "HH:MM"
    }
}

# Метрики для daily опроса
METRICS = {
    "sleep_hours": {
        "question": "Дополнительный сон (часов)?",
        "measurement": "hours"
    },
    "sleep_time": {
        "question": "Во сколько лёг спать?", # Removed (HH:MM)
        "measurement": "time"
    },
    "wake_time": {
        "question": "Во сколько проснулся?", # Removed (HH:MM)
        "measurement": "time"
    },
    "productivity_hours": {
        "question": "Продуктивность (часов)?",
        "measurement": "hours"
    },
    "meditate_minutes": {
        "question": "Сколько минут медитировал?",
        "measurement": "minutes"
    },
    "energy": {
        "question": "Уровень энергии?",
        "measurement": "scale_10"
    },
    "anxiety": {
        "question": "Уровень тревоги?",
        "measurement": "scale_10"
    },
    "irritability": {
        "question": "Раздражительность?",
        "measurement": "scale_10"
    },
    "racing_thoughts": {
        "question": "Ускоренные мысли и речь?",
        "measurement": "scale_10"
    },
    "smoked": {
        "question": "Сколько косяков выкурил?",
        "measurement": "count"
    },
    "modafinil": {
        "question": "Принимал модафинил?",
        "measurement": "yes_no"
    },
    "yoga": {
        "question": "Йога?",
        "measurement": "yes_no"
    },
    "mood_note": {
        "question": "Что тебя беспокоит? (текст/войс/пропустить)",
        "measurement": "note"
    }
}


# Вспомогательная функция для получения конфига measurement
def get_measurement_config(metric_key):
    """Возвращает полный конфиг measurement для метрики."""
    if metric_key not in METRICS:
        return {}
    metric = METRICS[metric_key]
    measurement_type = metric["measurement"]
    return MEASUREMENT_TYPES.get(measurement_type, {})

def is_metric_summable(metric_key):
    """Проверяет, является ли метрика суммируемой."""
    cfg = get_measurement_config(metric_key)
    return cfg.get("is_summable", False)
