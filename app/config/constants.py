"""
Константы приложения — сетевые порты, лимиты и диапазоны значений.
Используются для валидации API и конфигурации коллекторов.
"""

# === Сетевые порты ===
S7_DEFAULT_PORT = 102          # ISO-on-TCP (Siemens S7)
ETHERNET_IP_DEFAULT_PORT = 44818  # EtherNet/IP (Allen-Bradley)
SIMULATOR_DEFAULT_PORT = 2000  # Встроенный snap7-симулятор

# === Лимиты длины строк ===
MAX_NAME_LENGTH = 100          # Имя PLC / тега
MAX_AB_TAG_NAME_LENGTH = 255   # Имя Allen-Bradley тега

# === Диапазоны валидации S7 ===
DB_NUMBER_MIN = 1
DB_NUMBER_MAX = 65535
START_ADDRESS_MIN = 0
START_ADDRESS_MAX = 65535
BIT_NUMBER_MIN = 0
BIT_NUMBER_MAX = 7
RACK_MIN = 0
RACK_MAX = 7
SLOT_MIN = 0
SLOT_MAX = 31
AB_SLOT_MIN = 0
AB_SLOT_MAX = 16

# === Сетевые порты (диапазон) ===
TCP_PORT_MIN = 1
TCP_PORT_MAX = 65535

# === Опрос тегов ===
POLL_INTERVAL_MIN_MS = 100
POLL_INTERVAL_MAX_MS = 60000
DEFAULT_POLL_INTERVAL_MS = 1000

# === Области памяти S7 ===
S7_MEMORY_AREAS = ("DB", "I", "Q", "M", "T", "C")

# === Типы данных ===
VALID_DATA_TYPES = frozenset({"int", "dint", "real", "bool", "word", "dword", "string"})

# Размеры типов данных S7 (байты)
DATA_TYPE_SIZES = {
    "bool": 1,
    "int": 2,
    "word": 2,
    "dint": 4,
    "dword": 4,
    "real": 4,
    "string": 256,
}


def get_data_size(data_type: str) -> int:
    """Размер данных по типу; default=4 для неизвестных."""
    return DATA_TYPE_SIZES.get(data_type.lower(), 4)