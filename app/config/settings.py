import os
from pathlib import Path

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === База данных ===
# SQLite по умолчанию (файл в корне проекта)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'trends.db'}"
)

# === Настройки сбора данных ===
DEFAULT_POLL_INTERVAL_MS = 1000  # Интервал опроса по умолчанию (мс)
RECONNECT_DELAY_SEC = 2         # Задержка перед повторным подключением к ПЛК

# === Настройки хранения трендов ===
TREND_RETENTION_DAYS = 30       # Сколько дней хранить данные трендов
BATCH_INSERT_SIZE = 100         # Размер пакета для вставки данных

# === API настройки ===
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))


