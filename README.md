# 📊 Trends

Система сбора и визуализации трендов с ПЛК Siemens S7 и Allen-Bradley.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Возможности

- 🔌 **Siemens S7** — S7-300/400/1200/1500 (PROFINET/S7Comm)
- 🔌 **Allen-Bradley** — ControlLogix/CompactLogix (EtherNet/IP)
- 📈 Автоматический сбор данных в реальном времени
- 💾 Хранение трендов в SQLite
- 🌐 **Веб-интерфейс** для настройки и визуализации
- 🔍 **Browse PLC** — просмотр блоков и тегов прямо из ПЛК
- 🎨 Красивые интерактивные графики (Chart.js)
- 🏠 Встроенный симулятор для тестирования (S7 + AB)
- ⏸️ Активация/деактивация опроса ПЛК
- 🔄 Автоматический перезапуск при изменении конфигурации

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
# Запуск
python run.py

# Запуск в режиме симуляции (для тестирования)
python run.py --simulate
```

Откройте **http://127.0.0.1:8000** в браузере.

При первом запуске:

1. **Добавьте ПЛК** — выберите тип (Siemens S7 / Allen-Bradley), укажите IP и параметры
2. **Настройте теги** — добавьте переменные для опроса или используйте Browse
3. **Смотрите тренды** — данные автоматически собираются и отображаются

## 🔌 Поддерживаемые ПЛК

### Siemens S7

- **Модели**: S7-300, S7-400, S7-1200, S7-1500
- **Протокол**: S7Comm (PROFINET)
- **Области памяти**: DB, I (Inputs), Q (Outputs), M (Markers), T (Timers), C (Counters)
- **Типы данных**: BOOL, BYTE, WORD, DWORD, INT, DINT, REAL

### Allen-Bradley

- **Модели**: ControlLogix, CompactLogix
- **Протокол**: EtherNet/IP (CIP)
- **Теги**: Controller-scope и Program-scope
- **Типы данных**: BOOL, SINT, INT, DINT, REAL, массивы

## 🖥️ Веб-интерфейс

### Sidebar (левая панель)
- **PLCs** — список ПЛК с индикаторами статуса (🟢/🔴/🟡)
  - ⏸️/▶️ — активация/деактивация опроса
  - ✏️ — редактирование
  - 🗑️ — удаление
- **TAGs** — теги выбранного ПЛК
  - 🔍 **Browse** — просмотр тегов/блоков из ПЛК
  - ➕ — добавить тег вручную

### Главный экран
- 📊 Графики трендов в реальном времени
- 📈 Статистика: мин, макс, среднее, количество точек
- ⏱️ Выбор периода: 5 мин, 15 мин, 1 час, 6 часов, 24 часа

### Browse PLC (🔍)

**Для Siemens S7:**
- Отображает сводку блоков (OB, FB, FC, DB)
- Список Data Blocks с размерами
- Быстрое добавление тегов из областей I, Q, M, T, C

**Для Allen-Bradley:**
- Полный список тегов из ПЛК
- Фильтрация по имени
- Отображение типа данных и размерности массивов
- Добавление тегов одним кликом

## ⚙️ Конфигурация

Системные настройки в `config.yaml`:

```yaml
# База данных
database:
  url: "sqlite:///data/trends.db"

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
  file: "logs/trends.log"

# Хранение данных
retention:
  days: 30                    # Хранить данные 30 дней
  cleanup_interval_hours: 6   # Очистка каждые 6 часов
```

> 💡 **ПЛК и теги настраиваются через веб-интерфейс**, не в config.yaml!

## 🏠 Режим симуляции

Для тестирования без реального ПЛК:

```bash
python run.py --simulate
```

Автоматически создаются:

### SimPLC (Siemens S7)
- 🌡️ **RoomTemperature** — температура (DB1.REAL0)
- 💧 **RoomHumidity** — влажность (DB1.REAL4)
- ⚡ **InputVoltage** — напряжение (I0)
- 🔌 **OutputPower** — мощность (Q0)
- 📊 **Pressure** — давление (M0)
- ⏱️ **Uptime** — время работы (T0)
- 🔢 **CycleCount** — счётчик циклов (C0)

### SimAB (Allen-Bradley)
- 🌡️ **Temperature** — температура
- 📊 **Pressure** — давление
- 💧 **FlowRate** — расход
- 🔢 **ProductCount** — счётчик продукции
- ⚙️ **Motor_Running** — статус двигателя

Browse для SimAB возвращает 23 симулированных тега разных типов.

## 📊 REST API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/status` | Статус коллектора |
| GET | `/api/plcs` | Список ПЛК |
| POST | `/api/plcs` | Добавить ПЛК |
| PUT | `/api/plcs/{id}` | Обновить ПЛК |
| DELETE | `/api/plcs/{id}` | Удалить ПЛК |
| POST | `/api/plcs/{id}/toggle` | Активировать/деактивировать ПЛК |
| GET | `/api/plcs/{id}/browse` | Получить список тегов/блоков из ПЛК |
| GET | `/api/tags` | Список тегов |
| GET | `/api/tags?plc_id=1` | Теги конкретного ПЛК |
| POST | `/api/tags` | Добавить тег |
| PUT | `/api/tags/{id}` | Обновить тег |
| DELETE | `/api/tags/{id}` | Удалить тег |
| GET | `/api/tags/{id}/trend` | Данные тренда |
| GET | `/api/tags/{id}/statistics` | Статистика тега |
| POST | `/api/collector/restart` | Перезапуск коллектора |

## 🏗️ Структура проекта

```
trends/
├── app/
│   ├── api/
│   │   └── server.py              # FastAPI сервер
│   ├── collectors/
│   │   ├── S7Comm/
│   │   │   └── siemens_s7.py      # Клиент Siemens S7
│   │   └── EtherNetIP/
│   │       └── allen_bradley.py   # Клиент Allen-Bradley
│   ├── config/
│   │   └── config_loader.py       # Загрузчик YAML
│   ├── services/
│   │   ├── collector_service.py   # Сервис сбора данных
│   │   ├── collector_manager.py   # Управление коллектором
│   │   ├── collector_status.py    # Статус подключений
│   │   ├── runtime_config.py      # Runtime настройки
│   │   └── trend_service.py       # Работа с трендами
│   └── storage/
│       ├── database.py            # Подключение к БД
│       └── models.py              # Модели SQLAlchemy
├── web/
│   └── templates/
│       └── index.html             # Веб-интерфейс
├── data/                          # База данных SQLite
├── logs/                          # Логи
├── tests/                         # Тесты
├── config.yaml                    # Системные настройки
├── requirements.txt               # Зависимости
├── run.py                         # Точка входа
└── README.md
```

## 🖥️ Windows-приложение

### Сборка .exe

```bash
# Сборка приложения
.\venv\Scripts\pyinstaller.exe trends.spec --noconfirm

# Или через build.bat
.\build.bat
```

Готовый `Trends.exe` появится в папке `dist/`.

### Запуск

1. Запустите `Trends.exe`
2. В системном трее появится иконка 📊
3. Браузер автоматически откроется на http://127.0.0.1:8000
4. Правый клик по иконке → меню (Открыть в браузере / Выход)

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
- **python-snap7** — связь с Siemens S7
- **pycomm3** — связь с Allen-Bradley
- FastAPI + Uvicorn — веб-сервер
- SQLAlchemy 2.0+ — ORM
- Chart.js — графики
- pystray + Pillow — системный трей (Windows)

## 📄 Лицензия

MIT License
