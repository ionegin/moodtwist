# survey_provider.py
"""
Единственный источник правды о метриках и опросах — файл PASTE_SURVEY_HERE.json.

В файле два варианта источника:
  - "url": публичная ссылка на JSON (если заполнена — бот тянет опрос по ней);
  - "inline": сам JSON текстом (используется, когда "url" пуст).

Порядок загрузки (один кэш для опроса и редактирования):
  1. читаем PASTE_SURVEY_HERE.json → url или inline → валидация;
  2. при ошибке — диск data/survey_schema.json (даже протухший);
  3. иначе — пустая fallback-схема (опрос «временно недоступен»).

Все accessor-ы синхронные и читают уже загруженную схему.
"""
import copy
import json
import logging
import time
from pathlib import Path

from config import BASE_DIR, SURVEY_CACHE_TTL
from question_types import QUESTION_TYPES, aggregate as aggregate_by_type

SCHEMA_VERSION = 1
FALLBACK_SCHEMA = {"schema_version": 1, "metrics": {}, "surveys": {}}
SOURCE_PATH = Path(BASE_DIR) / "PASTE_SURVEY_HERE.json"
CACHE_PATH = Path(BASE_DIR) / "data" / "survey_schema.json"

_schema = None
_loaded_at = None


# ─── Правила вычисления метрик с computed_from ───────────────────────────────

def _compute_time_diff_hours(values):
    """Разница двух строк ЧЧ:ММ в часах (с переходом через полночь)."""
    try:
        sleep_time, wake_time = values
        sh, sm = map(int, sleep_time.replace(".", ":").split(":"))
        wh, wm = map(int, wake_time.replace(".", ":").split(":"))
        sleep_minutes = sh * 60 + sm
        wake_minutes = wh * 60 + wm
        diff = wake_minutes - sleep_minutes
        if diff < 0:
            diff += 24 * 60
        return round(diff / 60, 2)
    except Exception:
        return None


COMPUTE_RULES = {
    "time_diff_hours": _compute_time_diff_hours,
}


# ─── Загрузка схемы ───────────────────────────────────────────────────────────

async def load_schema():
    global _schema, _loaded_at
    now = time.time()
    if _schema is not None and _loaded_at is not None and (now - _loaded_at) < SURVEY_CACHE_TTL:
        return _schema

    fetched = None
    source = _read_source_file()
    if source is None:
        logging.error("[SURVEY] %s missing or invalid", SOURCE_PATH.name)

    url = (source or {}).get("url") or ""
    inline = (source or {}).get("inline")

    if url.strip():
        try:
            text = await _fetch_url(url.strip())
            parsed = json.loads(text)
        except Exception as e:
            parsed = None
            logging.error("[SURVEY] url fetch/parse failed: %s", e)
        if parsed is not None and _validate_schema(parsed):
            fetched = parsed
            logging.info("[SURVEY] schema fetched from url (%d metrics)", len(parsed.get("metrics", {})))
        else:
            logging.error("[SURVEY] fetched schema failed validation; trying inline fallback")
            if _validate_schema(inline):
                fetched = inline
                logging.warning("[SURVEY] using inline fallback from %s", SOURCE_PATH.name)
    else:
        if _validate_schema(inline):
            fetched = inline
            logging.info("[SURVEY] using inline schema from %s", SOURCE_PATH.name)
        else:
            logging.error("[SURVEY] inline schema invalid")

    if fetched is not None:
        _schema = fetched
        _write_disk_cache(fetched)
    else:
        disk = _load_disk_cache()
        if disk is not None:
            _schema = disk
            logging.warning("[SURVEY] using disk cache")
        else:
            _schema = copy.deepcopy(FALLBACK_SCHEMA)
            logging.error("[SURVEY] using EMPTY fallback schema")

    _loaded_at = time.time()
    return _schema


def reset_schema():
    global _schema, _loaded_at
    _schema = None
    _loaded_at = None


def _read_source_file():
    """Читает PASTE_SURVEY_HERE.json, возвращает dict или None."""
    try:
        if SOURCE_PATH.exists():
            text = SOURCE_PATH.read_text(encoding="utf-8")
            try:
                return json.loads(text)
            except Exception as e:
                # Файл сломан при ручном редактировании — всё равно вытаскиваем url,
                # чтобы бот мог скачать схему с Google Drive.
                import re
                m = re.search(r'"url"\s*:\s*"([^"]+)"', text)
                if m:
                    logging.warning(
                        "[SURVEY] %s invalid JSON, recovered url from it", SOURCE_PATH.name
                    )
                    return {"url": m.group(1)}
                raise
    except Exception as e:
        logging.error("[SURVEY] source file read failed: %s", e)
    return None


def _extract_drive_file_id(url):
    """Достаёт file id из ссылки Google Drive или возвращает None."""
    import re
    m = re.search(r"(?:/file/d/|\bid=)([\w-]{25,})", url)
    return m.group(1) if m else None


_drive_token_cache = {"token": None, "expires_at": 0.0}


def _drive_token():
    """OAuth-токен сервис-аккаунта (с кэшем до истечения)."""
    import time as _time
    from datetime import datetime, timezone

    token = _drive_token_cache["token"]
    if token and _time.time() < _drive_token_cache["expires_at"] - 60:
        return token

    from config import CREDENTIALS_FILE
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    creds.refresh(Request())
    expiry = creds.expiry
    if expiry is None:
        lifetime = 3600.0
    elif expiry.tzinfo is None:
        lifetime = (expiry - datetime.utcnow()).total_seconds()
    else:
        lifetime = (expiry - datetime.now(timezone.utc)).total_seconds()
    if lifetime <= 0:
        lifetime = 3600.0
    _drive_token_cache["token"] = creds.token
    _drive_token_cache["expires_at"] = _time.time() + lifetime
    return creds.token


async def _fetch_url(url):
    """Скачивает JSON по ссылке.

    Google Drive ссылки качаются через Drive API от имени сервис-аккаунта,
    поэтому работает и для приватных файлов, расшаренных на него.
    """
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=20)
    file_id = _extract_drive_file_id(url)
    if file_id:
        headers = {"Authorization": "Bearer " + _drive_token()}
        download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(download_url, headers=headers) as resp:
                if resp.status == 404:
                    raise PermissionError(
                        "[SURVEY] Google Drive file недоступен сервис-аккаунту "
                        "(нет доступа или файл удалён)"
                    )
                resp.raise_for_status()
                return await resp.text()
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()


def set_survey_url(url):
    """Записывает активную ссылку на опрос в PASTE_SURVEY_HERE.json (inline сохраняется)."""
    url = (url or "").strip()
    data = _read_source_file() or {}
    data["// previous url"] = data.get("url", "")
    data["url"] = url
    try:
        SOURCE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logging.error("[SURVEY] could not write %s: %s", SOURCE_PATH.name, e)
        raise
    reset_schema()
    return url


def _validate_schema(data):
    if not isinstance(data, dict):
        return False
    if data.get("schema_version") != SCHEMA_VERSION:
        return False
    metrics = data.get("metrics")
    surveys = data.get("surveys")
    if not isinstance(metrics, dict) or not isinstance(surveys, dict):
        return False
    for key, metric in metrics.items():
        if not isinstance(metric, dict):
            return False
        type_name = metric.get("type")
        if type_name not in QUESTION_TYPES:
            return False
        if "question" not in metric:
            return False
        computed_from = metric.get("computed_from")
        if computed_from is not None:
            if not isinstance(computed_from, list) or not computed_from:
                return False
            for src in computed_from:
                if src not in metrics:
                    return False
        if "compute" in metric and "computed_from" not in metric:
            return False
    for survey_name, survey in surveys.items():
        if not isinstance(survey, dict) or not isinstance(survey.get("metrics"), list):
            return False
        for metric_key in survey["metrics"]:
            if metric_key not in metrics:
                return False
    return True


def _load_disk_cache():
    try:
        if CACHE_PATH.exists():
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if _validate_schema(data):
                return data
            logging.error("[SURVEY] disk cache invalid, ignoring")
    except Exception as e:
        logging.error("[SURVEY] disk cache read failed: %s", e)
    return None


def _write_disk_cache(data):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error("[SURVEY] disk cache write failed: %s", e)


# ─── Accessor-ы ───────────────────────────────────────────────────────────────

def get_metric(key):
    """Возвращает запись метрики из схемы или None."""
    if not _schema:
        return None
    return _schema.get("metrics", {}).get(key)


def get_type(key):
    """Возвращает тип метрики (scale/number/yes_no/time/note/word) или None."""
    metric = get_metric(key)
    return metric.get("type") if metric else None


def get_metric_config(key):
    """Объединяет дефолты типа и поля метрики из схемы."""
    metric = get_metric(key)
    if not metric:
        return {}
    type_def = QUESTION_TYPES.get(metric.get("type"), {})
    cfg = {k: v for k, v in type_def.items() if not callable(v)}
    cfg.update(metric)
    return cfg


def is_computed(key):
    """True, если значение метрики вычисляется (computed_from)."""
    metric = get_metric(key)
    return bool(metric and metric.get("computed_from"))


def list_metrics():
    """Все ключи метрик в порядке схемы."""
    if not _schema:
        return []
    return list(_schema.get("metrics", {}).keys())


def list_of_type(type_name):
    """Ключи метрик заданного типа в порядке схемы."""
    return [k for k in list_metrics() if get_type(k) == type_name]


def list_summable():
    """Метрики для quick-add (все number)."""
    return list_of_type("number")


def list_yes_no():
    """Метрики типа yes_no."""
    return list_of_type("yes_no")


def get_survey_metrics(name):
    """Список метрик опроса по имени (daily/mood) или None."""
    if not _schema:
        return None
    survey = _schema.get("surveys", {}).get(name)
    if not survey:
        return None
    return list(survey.get("metrics", []))


def get_button_label(key):
    """Лейбл кнопки меню редактирования (button из JSON или question)."""
    cfg = get_metric_config(key)
    return cfg.get("button") or cfg.get("question") or key


def get_yesno_group_label():
    """Единая кнопка-группа для yes_no метрик (лейблы через « / »)."""
    labels = [get_button_label(k) for k in list_yes_no()]
    return " / ".join(labels) if labels else None


def compute_metric(key, answers):
    """Вычисляет значение метрики с computed_from из словаря ответов."""
    metric = get_metric(key)
    if not metric:
        return None
    compute = metric.get("compute")
    if not compute:
        return None
    rule = COMPUTE_RULES.get(compute)
    if not rule:
        return None
    sources = metric.get("computed_from", [])
    values = [answers.get(s) for s in sources]
    if any(v is None for v in values):
        return None
    return rule(values)


def aggregate(key, values):
    """Агрегирует список значений колонки за день по типу метрики."""
    type_name = get_type(key)
    if not type_name:
        return None
    return aggregate_by_type(type_name, values)

