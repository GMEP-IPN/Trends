# 📊 Trends Collector

Система сбора и хранения трендов с ПЛК Siemens S7.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Tests](https://img.shields.io/badge/Tests-38%20passed-success.svg)
![Coverage](https://img.shields.io/badge/Coverage-51%25-yellow.svg)

## 🎯 Возможности

- 🔌 Подключение к ПЛК Siemens S7-300/400/1200/1500
- 📈 Автоматический сбор данных по расписанию
- 💾 Хранение трендов в SQLite/PostgreSQL
- 🔧 Настройка через YAML-конфиг (без кода)
- 🏠 Встроенный симулятор для тестирования
- 📊 API для получения статистики
- 🧪 Покрытие тестами

## 📦 Установка

```bash
# Клонирование репозитория
git clone https://github.com/your-repo/trends.git
cd trends

# Создание виртуального окружения
python -m venv venv

# Активация (Windows)
.\venv\Scripts\activate

# Активация (Linux/Mac)
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

## ⚙️ Конфигурация

Настройки хранятся в `config.yaml`:

```yaml
# Настройки базы данных
database:
  url: "sqlite:///trends.db"

# Настройки сбора
collector:
  batch_size: 10
  flush_interval_sec: 5

# Конфигурация ПЛК
plcs:
  - name: "MainPLC"
    ip: "192.168.1.10"
    port: 102
    rack: 0
    slot: 1              # S7-1200: 1, S7-300/400: 2
    enabled: true
    
    tags:
      - name: "Temperature"
        db: 1
        address: 0
        type: "real"     # int, dint, real, bool, word
        size: 4
        poll_ms: 1000
```

## 🚀 Использование

### Основные команды

```bash
# Инициализация БД из config.yaml
python run.py --init

# Проверка подключения к ПЛК
python run.py --test-connection

# Показать настроенные теги
python run.py --list-tags

# Статус системы
python run.py --status

# Запуск сбора данных (продакшен)
python run.py

# Запуск в режиме симуляции (для тестов)
python run.py --simulate
# или короткая форма
python run.py -s
```

### Режим симуляции

Для тестирования без реального ПЛК:

```bash
python run.py --simulate
```

Симулятор генерирует реалистичные данные:
- 🌡️ Температура: колебания вокруг 22°C
- 💧 Влажность: 40-50%

## 🏗️ Структура проекта

```
trends/
├── app/
│   ├── api/                 # REST API (будущее)
│   ├── collectors/
│   │   └── S7Comm/
│   │       ├── plcsim.py    # Симулятор ПЛК
│   │       └── siemens_s7.py # Клиент S7
│   ├── config/
│   │   ├── config_loader.py # Загрузчик YAML
│   │   └── settings.py      # Настройки
│   ├── services/
│   │   ├── collector_service.py  # Сервис сбора
│   │   └── trend_service.py      # Работа с трендами
│   └── storage/
│       ├── database.py      # Подключение к БД
│       └── models.py        # Модели SQLAlchemy
├── tests/                   # Тесты
├── logs/                    # Логи
├── config.yaml              # Конфигурация
├── requirements.txt         # Зависимости
└── run.py                   # Точка входа
```

## 📊 Модели данных

### PLC
| Поле | Тип | Описание |
|------|-----|----------|
| name | str | Уникальное имя ПЛК |
| ip_address | str | IP адрес |
| tcp_port | int | Порт (102 по умолчанию) |
| rack | int | Rack (обычно 0) |
| slot | int | Slot (1 или 2) |

### Tag
| Поле | Тип | Описание |
|------|-----|----------|
| name | str | Имя тега |
| db_number | int | Номер DB блока |
| start_address | int | Байтовый адрес |
| data_type | str | Тип: int, dint, real, bool |
| poll_interval_ms | int | Интервал опроса (мс) |

### TrendData
| Поле | Тип | Описание |
|------|-----|----------|
| tag_id | int | ID тега |
| timestamp | datetime | Время записи |
| value | float | Значение |
| quality | int | Качество (192 = Good) |

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app

# Конкретный файл
pytest tests/test_models.py

# Verbose режим
pytest -v
```

## 📝 API сервисов

### TrendService

```python
from app.services import get_trend_data, get_latest_value, get_statistics

# Получить данные за период
data = get_trend_data(tag_id=1, start_time=..., end_time=...)

# Последнее значение
timestamp, value = get_latest_value(tag_id=1)

# Статистика
stats = get_statistics(tag_id=1)
# {'min': 20.0, 'max': 25.0, 'avg': 22.5, 'count': 100}
```

## 🔧 Требования

- Python 3.10+
- snap7 (для связи с ПЛК)
- SQLAlchemy 2.0+
- PyYAML

## 📄 Лицензия

MIT License

## 👥 Авторы

- Разработано с помощью Cursor AI

