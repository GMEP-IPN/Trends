# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Trends** — система сбора и визуализации данных с промышленных ПЛК (Siemens S7 и Allen-Bradley). Включает FastAPI-сервер, SQLite-хранилище трендов, Web UI с графиками и встроенный симулятор.

## Commands

```bash
# Run (normal mode)
python run.py

# Run with built-in PLC simulator (no hardware needed)
python run.py --simulate

# Check system status
python run.py --status

# Tests
pytest
pytest --cov=app
pytest tests/test_api.py          # single test file
pytest -k "test_name"             # single test by name

# Build Windows .exe (Windows only)
.\build.bat
```

Web UI: http://127.0.0.1:8000

## Architecture

```
app/
  api/server.py              # FastAPI REST API — all HTTP endpoints
  collectors/
    S7Comm/siemens_s7.py     # Siemens S7 client (python-snap7)
    EtherNetIP/allen_bradley.py  # Allen-Bradley client (pycomm3)
  config/
    config_loader.py         # Loads config.yaml
    settings.py              # Runtime settings singleton
  services/
    collector_manager.py     # Top-level orchestrator — starts/stops everything
    collector_service.py     # Per-PLC polling thread
    collector_status.py      # Connection status tracking
    runtime_config.py        # In-memory runtime config
    trend_service.py         # Trend data queries
  storage/
    database.py              # SQLAlchemy engine/session
    models.py                # ORM models: PLC, Tag, TrendData
web/templates/index.html     # Single-page UI (Chart.js, ~110 KB)
tests/                       # 10 pytest files
config.yaml                  # Main config (DB URL, ports, retention, etc.)
run.py                       # CLI entry point
trends_app.py                # Windows system-tray desktop wrapper
trends.spec                  # PyInstaller spec → dist/Trends/Trends.exe
```

### Data flow

`collector_manager` starts a `collector_service` thread per active PLC → threads poll PLC tags at the configured interval → values written to `trend_data` table in batches → `server.py` serves REST API for the UI.

### Simulator mode (`--simulate`)

Creates two virtual PLCs in the database (SimPLC for S7, SimAB for Allen-Bradley) with pre-configured tags and starts fake snap7 / EtherNet/IP servers that return synthetic sine-wave / counter values.

## Key REST endpoints (server.py)

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/plcs` | List / create PLCs |
| GET/PUT/DELETE | `/api/plcs/{id}` | PLC detail / edit / delete |
| GET/POST | `/api/tags` | List / create tags |
| GET | `/api/tags/{id}/trend` | Time-series data |
| GET | `/api/tags/{id}/statistics` | Min/max/avg |
| GET | `/api/plcs/{id}/browse` | Live PLC tag browser |
| POST | `/api/collector/restart` | Restart collector threads |

## Database

SQLite at `DB/trends.db` (path from `config.yaml`). Three tables: `plcs`, `tags`, `trend_data`. Retention cleanup runs every 6 hours (configurable in config.yaml → `storage.retention_days`).

## Python version

Requires Python 3.10+. No virtual-env is committed; install dependencies with:
```bash
pip install -r requirements.txt
```
`snap7` native library must also be present on the system for S7 communication (not needed in simulate mode).
