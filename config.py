print("VERSION 7 env hierarchy")

import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем папку, где лежит этот файл
BASE_DIR = Path(__file__).resolve().parent


def _load_env_file() -> Path | None:
    """Load env values from a local .env file when it exists."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        print(f"DEBUG: loaded env from {env_path}")
        return env_path

    print("DEBUG: no local .env file found; using environment variables")
    return None


def _get_setting(key: str, default: str | None = None) -> str | None:
    """Read a single environment variable value."""
    value = os.getenv(key)
    if value:
        return value
    return default


def _find_local_credentials() -> str | None:
    """Find a local credentials JSON file in the project folder."""
    candidates = [BASE_DIR / "borderliner-credentials.json", BASE_DIR / "secret_credentials.json"]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


_load_env_file()

# CREDENTIALS_CONTENT — JSON в переменной, создаём временный файл.
# Если уже задан путь к файлу credentials, используем его.
credentials_content = _get_setting("CREDENTIALS_CONTENT")
credentials_path = _get_setting("CREDENTIALS_PATH")
if not credentials_path:
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Если путь к credentials не задан, ищем локальный файл в папке проекта.
if not credentials_path and not credentials_content:
    local_credentials = _find_local_credentials()
    if local_credentials:
        credentials_path = local_credentials
        os.environ["CREDENTIALS_PATH"] = credentials_path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        print(f"DEBUG: found local credentials file at {credentials_path}")

if credentials_content:
    resolved_credentials_path = credentials_path or str(BASE_DIR / "secret_credentials.json")
    with open(resolved_credentials_path, "w", encoding="utf-8") as f:
        f.write(credentials_content)
    os.environ["CREDENTIALS_PATH"] = resolved_credentials_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = resolved_credentials_path
    print(f"DEBUG: created credentials file from CREDENTIALS_CONTENT at {resolved_credentials_path}")
elif credentials_path:
    os.environ["CREDENTIALS_PATH"] = credentials_path
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    print(f"DEBUG: using credentials file from path {credentials_path}")
else:
    print("DEBUG: CREDENTIALS_CONTENT is empty or missing and no local credentials file found.")

CREDENTIALS_FILE = os.getenv("CREDENTIALS_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or str(BASE_DIR / "borderliner-credentials.json")

print(f"DEBUG CREDENTIALS_FILE final: {CREDENTIALS_FILE}")
print(f"DEBUG file exists: {os.path.exists(CREDENTIALS_FILE)}")

BOT_TOKEN = _get_setting("TELEGRAM_TOKEN")
GROQ_API_KEY = _get_setting("GROQ_KEY")
WEBHOOK_BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBHOOK_URL") or os.getenv("SPACE_HOST", "")
GOOGLE_SHEET_ID = _get_setting("GOOGLE_SHEET_ID", "1a6fCFKO2y6r04Z2U8N495nzN1S9-SEas_21ldnqFBcY")