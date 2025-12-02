# 📊 Trends Collector

Система сбора и визуализации трендов с ПЛК Siemens S7.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Возможности

- 🔌 Подключение к ПЛК Siemens S7-300/400/1200/1500
- 📈 Автоматический сбор данных в реальном времени
- 💾 Хранение трендов в SQLite/PostgreSQL
- 🌐 **Веб-интерфейс для настройки и визуализации**
- 🎨 Красивые интерактивные графики
- 🏠 Встроенный симулятор для тестирования
- 🔄 Горячая перезагрузка конфигурации

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

## 🚀 Быстрый старт

```bash
# Запуск (с веб-интерфейсом)
python run.py

# Запуск в режиме симуляции (для тестирования)
python run.py --simulate
```

Откройте **http://127.0.0.1:8000** в браузере.

При первом запуске появится мастер настройки:

1. **Добавьте ПЛК** — укажите IP, порт, rack, slot
2. **Настройте теги** — добавьте переменные для опроса
3. **Смотрите тренды** — данные автоматически собираются и отображаются

## 🖥️ Веб-интерфейс

### Главный экран
- 📊 Графики трендов в реальном времени
- 📈 Статистика: мин, макс, среднее
- ⚙️ Настройка ПЛК и тегов

### Настройка ПЛК
- ➕ Добавление нового ПЛК
- ✏️ Редактирование параметров подключения
- 🗑️ Удаление (с каскадным удалением тегов)
- 🔄 Перезапуск коллектора после изменений

### Настройка тегов
- Имя и описание
- DB-блок и адрес
- Тип данных: `real`, `int`, `dint`, `bool`, `word`
- Интервал опроса (мс)

## ⚙️ Конфигурация

Системные настройки в `config.yaml`:

```yaml
# База данных
database:
  url: "sqlite:///trends.db"

# Настройки сбора
collector:
  batch_size: 100
  flush_interval_sec: 5
  reconnect_delay_sec: 5

# API сервер
api:
  host: "127.0.0.1"
  port: 8000

# Логирование
logging:
  level: "INFO"
  file: "logs/collector.log"
```

> 💡 **ПЛК и теги настраиваются через веб-интерфейс**, не в config.yaml!

## 🏠 Режим симуляции

Для тестирования без реального ПЛК:

```bash
python run.py --simulate
```

Автоматически создаётся `SimPLC` с тегами:
- 🌡️ **RoomTemperature** — температура (20-25°C)
- 💧 **RoomHumidity** — влажность (40-50%)

## 📊 REST API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/status` | Статус коллектора |
| GET | `/api/plcs` | Список ПЛК |
| POST | `/api/plcs` | Добавить ПЛК |
| PUT | `/api/plcs/{id}` | Обновить ПЛК |
| DELETE | `/api/plcs/{id}` | Удалить ПЛК |
| GET | `/api/tags` | Список тегов |
| POST | `/api/tags` | Добавить тег |
| DELETE | `/api/tags/{id}` | Удалить тег |
| GET | `/api/tags/{id}/trend` | Данные тренда |
| GET | `/api/tags/{id}/statistics` | Статистика тега |
| POST | `/api/collector/restart` | Перезапуск коллектора |

## 🏗️ Структура проекта

```
trends/
├── app/
│   ├── api/
│   │   └── server.py           # FastAPI сервер
│   ├── collectors/
│   │   └── S7Comm/
│   │       └── siemens_s7.py   # Клиент S7
│   ├── config/
│   │   └── config_loader.py    # Загрузчик YAML
│   ├── services/
│   │   ├── collector_service.py  # Сервис сбора
│   │   └── trend_service.py      # Работа с трендами
│   └── storage/
│       ├── database.py         # Подключение к БД
│       └── models.py           # Модели SQLAlchemy
├── web/
│   └── templates/
│       └── index.html          # Веб-интерфейс
├── tests/                      # Тесты
├── config.yaml                 # Системные настройки
├── requirements.txt            # Зависимости
└── run.py                      # Точка входа
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app

# Verbose режим
pytest -v
```

## 🔧 Требования

- Python 3.10+
- python-snap7 (связь с ПЛК)
- FastAPI + Uvicorn (веб-сервер)
- SQLAlchemy 2.0+ (ORM)
- Chart.js (графики)

## 📄 Лицензия

MIT License
