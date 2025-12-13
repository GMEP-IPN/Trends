# 📊 Trends

Data collection and visualization system for Siemens S7 and Allen-Bradley PLCs.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Features

- 🔌 **Siemens S7** — S7-300/400/1200/1500 (PROFINET/S7Comm)
- 🔌 **Allen-Bradley** — ControlLogix/CompactLogix (EtherNet/IP)
- 📈 Real-time automatic data collection
- 💾 Trend storage in SQLite
- 🌐 **Web interface** for configuration and visualization
- 🔍 **Browse PLC** — view blocks and tags directly from PLC
- 🎨 Beautiful interactive charts (Chart.js)
- 🏠 Built-in simulator for testing (S7 + AB)
- ⏸️ Activate/deactivate PLC polling
- 🔄 Automatic restart on configuration changes

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/your-repo/trends.git
cd trends

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 🚀 Quick Start

```bash
# Run
python run.py

# Run in simulation mode (for testing)
python run.py --simulate
```

Open **http://127.0.0.1:8000** in your browser.

On first launch:

1. **Add PLC** — select type (Siemens S7 / Allen-Bradley), enter IP and parameters
2. **Configure tags** — add variables for polling or use Browse
3. **View trends** — data is automatically collected and displayed

## 🔌 Supported PLCs

### Siemens S7

- **Models**: S7-300, S7-400, S7-1200, S7-1500
- **Protocol**: S7Comm (PROFINET)
- **Memory areas**: DB, I (Inputs), Q (Outputs), M (Markers), T (Timers), C (Counters)
- **Data types**: BOOL, BYTE, WORD, DWORD, INT, DINT, REAL

### Allen-Bradley

- **Models**: ControlLogix, CompactLogix
- **Protocol**: EtherNet/IP (CIP)
- **Tags**: Controller-scope and Program-scope
- **Data types**: BOOL, SINT, INT, DINT, REAL, arrays

## 🖥️ Web Interface

### Sidebar (left panel)
- **PLCs** — PLC list with status indicators (🟢/🔴/🟡)
  - ⏸️/▶️ — activate/deactivate polling
  - ✏️ — edit
  - 🗑️ — delete
- **TAGs** — tags of selected PLC
  - 🔍 **Browse** — view tags/blocks from PLC
  - ➕ — add tag manually

### Main screen
- 📊 Real-time trend charts
- 📈 Statistics: min, max, average, point count
- ⏱️ Time range: 5 min, 15 min, 1 hour, 6 hours, 24 hours

### Browse PLC (🔍)

**For Siemens S7:**
- Displays block summary (OB, FB, FC, DB)
- List of Data Blocks with sizes
- Quick add tags from I, Q, M, T, C areas

**For Allen-Bradley:**
- Full tag list from PLC
- Filter by name
- Display data type and array dimensions
- Add tags with one click

## ⚙️ Configuration

System settings in `config.yaml`:

```yaml
# Database
database:
  url: "sqlite:///data/trends.db"

# Collector settings
collector:
  batch_size: 100
  flush_interval_sec: 5
  reconnect_delay_sec: 5

# API server
api:
  host: "127.0.0.1"
  port: 8000

# Logging
logging:
  level: "INFO"
  file: "logs/trends.log"

# Data retention
retention:
  days: 30                    # Keep data for 30 days
  cleanup_interval_hours: 6   # Cleanup every 6 hours
```

> 💡 **PLCs and tags are configured via web interface**, not in config.yaml!

## 🏠 Simulation Mode

For testing without a real PLC:

```bash
python run.py --simulate
```

Automatically created:

### SimPLC (Siemens S7)
- 🌡️ **RoomTemperature** — temperature (DB1.REAL0)
- 💧 **RoomHumidity** — humidity (DB1.REAL4)
- ⚡ **InputVoltage** — voltage (I0)
- 🔌 **OutputPower** — power (Q0)
- 📊 **Pressure** — pressure (M0)
- ⏱️ **Uptime** — uptime (T0)
- 🔢 **CycleCount** — cycle counter (C0)

### SimAB (Allen-Bradley)
- 🌡️ **Temperature** — temperature
- 📊 **Pressure** — pressure
- 💧 **FlowRate** — flow rate
- 🔢 **ProductCount** — product counter
- ⚙️ **Motor_Running** — motor status

Browse for SimAB returns 23 simulated tags of various types.

## 📊 REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Collector status |
| GET | `/api/plcs` | List PLCs |
| POST | `/api/plcs` | Add PLC |
| PUT | `/api/plcs/{id}` | Update PLC |
| DELETE | `/api/plcs/{id}` | Delete PLC |
| POST | `/api/plcs/{id}/toggle` | Activate/deactivate PLC |
| GET | `/api/plcs/{id}/browse` | Get tag/block list from PLC |
| GET | `/api/tags` | List tags |
| GET | `/api/tags?plc_id=1` | Tags of specific PLC |
| POST | `/api/tags` | Add tag |
| PUT | `/api/tags/{id}` | Update tag |
| DELETE | `/api/tags/{id}` | Delete tag |
| GET | `/api/tags/{id}/trend` | Trend data |
| GET | `/api/tags/{id}/statistics` | Tag statistics |
| POST | `/api/collector/restart` | Restart collector |

## 🏗️ Project Structure

```
trends/
├── app/
│   ├── api/
│   │   └── server.py              # FastAPI server
│   ├── collectors/
│   │   ├── S7Comm/
│   │   │   └── siemens_s7.py      # Siemens S7 client
│   │   └── EtherNetIP/
│   │       └── allen_bradley.py   # Allen-Bradley client
│   ├── config/
│   │   └── config_loader.py       # YAML loader
│   ├── services/
│   │   ├── collector_service.py   # Data collection service
│   │   ├── collector_manager.py   # Collector management
│   │   ├── collector_status.py    # Connection status
│   │   ├── runtime_config.py      # Runtime settings
│   │   └── trend_service.py       # Trend operations
│   └── storage/
│       ├── database.py            # DB connection
│       └── models.py              # SQLAlchemy models
├── web/
│   └── templates/
│       └── index.html             # Web interface
├── data/                          # SQLite database
├── logs/                          # Logs
├── tests/                         # Tests
├── config.yaml                    # System settings
├── requirements.txt               # Dependencies
├── run.py                         # Entry point
└── README.md
```

## 🖥️ Windows Application

### Build .exe

```bash
# Build application
.\venv\Scripts\pyinstaller.exe trends.spec --noconfirm

# Or via build.bat
.\build.bat
```

Ready `Trends.exe` will appear in `dist/` folder.

### Launch

1. Run `Trends.exe`
2. System tray icon 📊 will appear
3. Browser will automatically open http://127.0.0.1:8000
4. Right-click tray icon → menu (Open in browser / Exit)

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app

# Verbose mode
pytest -v
```

## 🔧 Requirements

- Python 3.10+
- **python-snap7** — Siemens S7 communication
- **pycomm3** — Allen-Bradley communication
- FastAPI + Uvicorn — web server
- SQLAlchemy 2.0+ — ORM
- Chart.js — charts
- pystray + Pillow — system tray (Windows)

## 📄 License

MIT License
