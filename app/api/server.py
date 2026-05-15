"""
REST API сервер для Trends Collector.
Тонкий HTTP-слой: парсит запросы, вызывает сервисы, сериализует ответы.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

import sys
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

# Определяем базовую директорию (для .exe и обычного запуска)
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).parent.parent.parent

from app import __version__
from app.api.schemas import (
    PLCCreateRequest,
    PLCCreateResponse,
    PLCResponse,
    TagCreateRequest,
    TagCreateResponse,
    TagResponse,
    TagTrendResponse,
    TagUpdateRequest,
    TrendPointResponse,
    StatisticsResponse,
    SystemStatusResponse,
)
from app.services import plc_service, tag_service, update_checker
from app.services.collector_status import collector_status
from app.services.trend_service import (
    get_trend_data,
    get_latest_value,
    get_latest_values_batch,
    get_statistics,
)
from app.storage import get_session, PLC, Tag, TrendData
from app.storage.models import PLC_TYPE_SIEMENS_S7, PLC_TYPE_ALLEN_BRADLEY

app = FastAPI(
    title="Trends Collector API",
    description="API для просмотра трендов с ПЛК",
    version=__version__,
)

# Статические файлы
static_path = _BASE_DIR / "web" / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

update_checker.start()

# === Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = _BASE_DIR / "web" / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("<h1>Trends</h1><p>UI not found. Check installation.</p>")


@app.get("/api/status", response_model=SystemStatusResponse)
async def get_status():
    with get_session() as session:
        plc_count = session.query(PLC).filter(PLC.is_active == True, PLC.is_archived == False).count()
        tag_count = session.query(Tag).join(PLC).filter(Tag.is_active == True, PLC.is_archived == False).count()
        trend_count = session.query(TrendData).count()

        last = session.query(TrendData).order_by(TrendData.timestamp.desc()).first()
        last_update = last.timestamp.isoformat() if last else None

        if collector_status.running:
            conn_status = "connected" if collector_status.connected else "disconnected"
        else:
            conn_status = "stopped"

        plc_errors = {}
        errors_by_id = collector_status.get_all_errors()
        if errors_by_id:
            plcs = session.query(PLC).filter(PLC.id.in_(errors_by_id.keys())).all()
            plc_names = {p.id: p.name for p in plcs}
            for plc_id, error in errors_by_id.items():
                plc_errors[plc_names.get(plc_id, f"PLC #{plc_id}")] = error

        upd = update_checker.get_info()
        return SystemStatusResponse(
            version=__version__,
            plc_count=plc_count,
            tag_count=tag_count,
            trend_count=trend_count,
            last_update=last_update,
            collector_running=collector_status.running,
            connection_status=conn_status,
            plc_errors=plc_errors,
            update_available=upd["update_available"],
            latest_version=upd["latest_version"],
            releases_url=upd["releases_url"],
        )


@app.get("/api/plcs", response_model=List[PLCResponse])
async def list_plcs(include_archived: bool = False):
    return [PLCResponse(**item) for item in plc_service.list_plcs(include_archived=include_archived)]


@app.post("/api/plcs", response_model=PLCCreateResponse)
async def create_plc(request: PLCCreateRequest):
    return PLCCreateResponse(**plc_service.create_plc(request))


@app.put("/api/plcs/{plc_id}")
async def update_plc(plc_id: int, request: PLCCreateRequest):
    return plc_service.update_plc(plc_id, request)


@app.delete("/api/plcs/{plc_id}")
async def delete_plc(plc_id: int):
    return plc_service.delete_plc(plc_id)


@app.put("/api/plcs/{plc_id}/toggle")
async def toggle_plc(plc_id: int):
    return plc_service.toggle_plc(plc_id)


@app.put("/api/plcs/{plc_id}/archive")
async def archive_plc(plc_id: int):
    return plc_service.archive_plc(plc_id)


@app.put("/api/plcs/{plc_id}/unarchive")
async def unarchive_plc(plc_id: int):
    return plc_service.unarchive_plc(plc_id)


@app.post("/api/collector/restart")
async def restart_collector():
    collector_status.request_restart()
    return {"message": "Restart requested", "status": "pending"}


@app.post("/api/update/check")
async def check_update():
    import asyncio
    await asyncio.get_event_loop().run_in_executor(None, update_checker._check)
    return update_checker.get_info()


@app.get("/api/plcs/{plc_id}/browse")
async def browse_plc(plc_id: int, program: str = None):
    """Browse PLC — возвращает теги/блоки, прочитанные с PLC напрямую."""
    plc = plc_service.get_plc_by_id(plc_id)
    if not plc:
        raise HTTPException(status_code=404, detail="PLC not found")

    plc_type = getattr(plc, "plc_type", PLC_TYPE_SIEMENS_S7)
    if plc_type == PLC_TYPE_ALLEN_BRADLEY:
        return await _browse_allen_bradley(plc, program)
    return await _browse_siemens_s7(plc)


async def _browse_siemens_s7(plc):
    """Browse Siemens S7 — получить список Data Blocks."""
    try:
        import snap7
        from snap7.type import Block

        client = snap7.client.Client()
        client.connect(plc.ip_address, plc.rack, plc.slot, plc.tcp_port)

        if not client.get_connected():
            raise HTTPException(status_code=503, detail="Cannot connect to PLC")

        blocks_info = client.list_blocks()

        db_list = []
        for db_num in range(1, 101):
            try:
                info = client.get_block_info(Block.DB, db_num)
                db_list.append({
                    "db_number": db_num,
                    "size": info.MC7Size,
                    "load_size": info.LoadSize if hasattr(info, "LoadSize") else None,
                })
            except Exception:
                pass

        client.disconnect()

        return {
            "plc_id": plc.id,
            "plc_name": plc.name,
            "plc_type": "siemens_s7",
            "connected": True,
            "blocks": {
                "OB": blocks_info.OBCount,
                "FB": blocks_info.FBCount,
                "FC": blocks_info.FCCount,
                "DB": blocks_info.DBCount,
            },
            "data_blocks": db_list,
            "memory_areas": ["I", "Q", "M", "T", "C"],
            "tags": [],
        }

    except ImportError:
        raise HTTPException(status_code=500, detail="snap7 library not available")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PLC browse failed: {str(e)}")


async def _browse_allen_bradley(plc, program: str = None):
    """Browse Allen-Bradley — полный список тегов из ПЛК."""
    from app.services.runtime_config import runtime_config

    if runtime_config.simulate_mode:
        return _get_simulated_ab_tags(plc)

    try:
        from pycomm3 import LogixDriver

        slot = getattr(plc, "slot_ab", 0) or 0
        path = f"{plc.ip_address}/{slot}" if slot > 0 else plc.ip_address

        with LogixDriver(path) as driver:
            tag_list = driver.get_tag_list(program=program or "*")
            tags = []
            for tag_info in tag_list:
                tag_data = {
                    "tag_name": tag_info.get("tag_name", ""),
                    "data_type": str(tag_info.get("data_type", "UNKNOWN")),
                    "data_type_name": tag_info.get("data_type_name", ""),
                    "dim": tag_info.get("dim", 0),
                    "external_access": tag_info.get("external_access", ""),
                }
                if tag_info.get("dimensions"):
                    tag_data["dimensions"] = tag_info["dimensions"]
                tags.append(tag_data)

            return {
                "plc_id": plc.id,
                "plc_name": plc.name,
                "plc_type": "allen_bradley",
                "connected": True,
                "tag_count": len(tags),
                "tags": tags,
                "data_blocks": [],
                "memory_areas": [],
            }

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pycomm3 library not installed. Run: pip install pycomm3",
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PLC browse failed: {str(e)}")


def _get_simulated_ab_tags(plc):
    """Симулированные теги для Allen-Bradley PLC в режиме --simulate."""
    simulated_tags = [
        {"tag_name": "Temperature", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Pressure", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "FlowRate", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Level", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Speed", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "TempSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "PressureSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "SpeedSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "ProductCount", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "BatchNumber", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "CycleCount", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "ErrorCode", "data_type": "INT", "data_type_name": "INT", "dim": 0},
        {"tag_name": "Status", "data_type": "INT", "data_type_name": "INT", "dim": 0},
        {"tag_name": "Motor_Running", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "Pump_On", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "Alarm_Active", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "SystemReady", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "EmergencyStop", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "TempArray", "data_type": "REAL", "data_type_name": "REAL", "dim": 1, "dimensions": [10]},
        {"tag_name": "IOStatus", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 1, "dimensions": [32]},
        {"tag_name": "Program:MainProgram.LocalVar1", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Program:MainProgram.Counter", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "Program:MainProgram.Running", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
    ]
    return {
        "plc_id": plc.id,
        "plc_name": plc.name,
        "plc_type": "allen_bradley",
        "connected": True,
        "tag_count": len(simulated_tags),
        "tags": simulated_tags,
        "data_blocks": [],
        "memory_areas": [],
    }


@app.get("/api/tags", response_model=List[TagResponse])
async def list_tags(plc_id: Optional[int] = None):
    """Список тегов с последними значениями (batch-запрос против N+1)."""
    with get_session() as session:
        query = session.query(Tag).join(PLC).filter(Tag.is_active == True, PLC.is_archived == False)
        if plc_id:
            query = query.filter(Tag.plc_id == plc_id)
        tags = query.all()

        latest_values = get_latest_values_batch([tag.id for tag in tags])

        return [
            TagResponse(
                id=tag.id,
                name=tag.name,
                description=tag.description,
                memory_area=getattr(tag, "memory_area", None) or "DB",
                db_number=tag.db_number,
                start_address=tag.start_address,
                bit_number=tag.bit_number or 0,
                data_type=tag.data_type,
                ab_tag_name=getattr(tag, "ab_tag_name", None),
                poll_interval_ms=tag.poll_interval_ms,
                latest_value=latest_values.get(tag.id)[1] if latest_values.get(tag.id) else None,
                latest_time=latest_values.get(tag.id)[0].isoformat() if latest_values.get(tag.id) else None,
            )
            for tag in tags
        ]


@app.get("/api/tags/{tag_id}/trend", response_model=List[TrendPointResponse])
async def get_tag_trend(
    tag_id: int,
    minutes: int = Query(default=60, ge=1, le=1440, description="Период в минутах"),
):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)
    data = get_trend_data(tag_id, start_time, end_time, limit=5000)
    return [
        TrendPointResponse(timestamp=ts.isoformat(), value=round(val, 2))
        for ts, val in data
    ]


@app.get("/api/trends", response_model=List[TagTrendResponse])
async def get_all_trends(
    plc_id: Optional[int] = None,
    minutes: int = Query(default=60, ge=1, le=1440, description="Период в минутах"),
):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)

    with get_session() as session:
        query = session.query(Tag).join(PLC).filter(Tag.is_active == True, PLC.is_archived == False)
        if plc_id:
            query = query.filter(Tag.plc_id == plc_id)
        tags = query.all()

        return [
            TagTrendResponse(
                tag_id=tag.id,
                tag_name=tag.name,
                data=[
                    TrendPointResponse(timestamp=ts.isoformat(), value=round(val, 2))
                    for ts, val in get_trend_data(tag.id, start_time, end_time, limit=5000)
                ],
            )
            for tag in tags
        ]


@app.get("/api/tags/{tag_id}/statistics", response_model=StatisticsResponse)
async def get_tag_statistics(
    tag_id: int,
    minutes: int = Query(default=60, ge=1, le=1440),
):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)
    return StatisticsResponse(**get_statistics(tag_id, start_time, end_time))


@app.get("/api/tags/{tag_id}/latest")
async def get_tag_latest(tag_id: int):
    result = get_latest_value(tag_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No data found")
    return {"timestamp": result[0].isoformat(), "value": round(result[1], 2)}


@app.post("/api/tags", response_model=TagCreateResponse)
async def create_tag(request: TagCreateRequest):
    return TagCreateResponse(**tag_service.create_tag(request))


@app.put("/api/tags/{tag_id}")
async def update_tag(tag_id: int, request: TagUpdateRequest):
    return tag_service.update_tag(tag_id, request)


@app.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: int):
    return tag_service.delete_tag(tag_id)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
