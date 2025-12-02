"""
Настройки приложения.
Значения загружаются из config.yaml через config_loader.
Этот файл содержит только константы по умолчанию.
"""
import os
from pathlib import Path

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === База данных ===
# Значение по умолчанию, реальное значение берётся из config.yaml
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'trends.db'}"
)

# === Настройки сбора данных ===
DEFAULT_POLL_INTERVAL_MS = 1000  # Интервал опроса по умолчанию (мс)
BATCH_INSERT_SIZE = 10          # Размер пакета для вставки данных

# Примечание: остальные настройки (retention_days, api_host/port, etc.)
# загружаются из config.yaml через config_loader.py
