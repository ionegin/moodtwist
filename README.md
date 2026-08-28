# moodtwist — Borderliner Bot

Telegram-дневник настроения и привычек: опросы → Google Sheets, заметки (текст/голос), пуш-напоминания. Бот — «тупой гейт»: типы вопросов и их логика фиксированы в коде, а сами вопросы лежат в одном внешнем JSON.

## Где живёт опрос (главное)

**`PASTE_SURVEY_HERE.json`** — единственный источник правды о вопросах:

```json
{
  "url": "",                     // публичная ссылка на JSON опроса (если заполнена — бот тянет по ней)
  "inline": {                    // сам JSON текстом (используется, когда "url" пуст)
    "schema_version": 1,
    "metrics": { "sleep_time": { "type": "time", "question": "..." }, ... },
    "surveys": { "daily": {"metrics": [...]}, "mood": {"metrics": [...]} }
  }
}
```

- Меняешь `inline` (или заполняешь `url`) → перезапусти бота, чтобы он перечитал файл.
- Кнопка бота **«🔗 Указать ссылку на вопросы»** пишет новую ссылку в `url` (inline остаётся как запас) и сразу перезагружает опрос.
- Кэш: in-memory (`SURVEY_CACHE_TTL`, сек.) + `data/survey_schema.json` (gitignored). Если источник битый — берётся кэш, иначе пустая схема (опрос «временно недоступен», заметки/войс работают).

**Внимание:** `inline` содержит реальные вопросы — не коммить их в публичный репозиторий, если это важно.

## Типы вопросов (логика в `question_types.py`)

| Тип | Вопрос | В опросе | Агрегация за день |
|---|---|---|---|
| `scale` | число 1–10 | каждый раз | среднее |
| `number` | «Сейчас X. Сколько ПРИБАВИТЬ?» + Оставить | каждый раз | сумма |
| `yes_no` | кнопки Да/Нет | один раз в день | последнее |
| `time` | ЧЧ:ММ | один раз в день | последнее |
| `note` | текст + Пропустить | каждый раз | нет (лист Notes) |
| `word` | одним словом (будущее) | — | нет |

Сутки считаются с **06:00** (UTC+2). Метрика с `computed_from` (напр. `sleep_hours` из `sleep_time`/`wake_time`) не спрашивается и вычисляется при сохранении.

## Карта файлов

| Файл | Зачем |
|---|---|
| `app.py` / `bot.py` | точка входа (long polling), FSM, обработчики |
| `PASTE_SURVEY_HERE.json` | **опрос: источник правды** |
| `question_types.py` | типы вопросов: рендер, валидация, агрегация |
| `survey_provider.py` | чтение опроса (url/inline), accessor-ы, кэш |
| `storage/sheets.py` | Google Sheets: запись/чтение, агрегация по типу |
| `menu.py` / `menu_config.py` | клавиатуры (edit/yesno_edit собираются из опроса) |
| `handlers.py` | команда `/start` |
| `services/transcription.py` | расшифровка голосовых (Groq) |
| `services/notifications.py` | пуш-напоминания (APScheduler) |
| `messages.py` | тексты напоминаний |
| `config.py` | env-переменные |

## Запуск

```bash
pip install -r requirements.txt
python app.py
```

Env-переменные: `TELEGRAM_TOKEN`, `GOOGLE_SHEET_ID`, `CREDENTIALS_PATH`/`CREDENTIALS_CONTENT` (сервис-аккаунт), `GROQ_KEY`, `SURVEY_CACHE_TTL`.

## Не трогать

- Ключи метрик в `metrics`/`surveys` — это колонки в Google Sheets.
- Сигнатуры `save_daily`, `save_note`, `transcribe_voice`.
- Голос/заметки/расшифровку.
- Не логировать значения ответов целиком.
