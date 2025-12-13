"""
REST API сервер для Trends Collector.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
import re

import sys
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, field_validator, model_validator

# Определяем базовую директорию (для .exe и обычного запуска)
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).parent.parent.parent

from app import __version__
from app.storage import get_session, PLC, Tag, TrendData
from app.storage.models import PLC_TYPE_SIEMENS_S7, PLC_TYPE_ALLEN_BRADLEY, PLC_TYPES
from app.services.trend_service import (
    get_trend_data, 
    get_latest_value,
    get_latest_values_batch,
    get_statistics,
    get_all_tags
)
from app.services.collector_status import collector_status

app = FastAPI(
    title="Trends Collector API",
    description="API для просмотра трендов с ПЛК",
    version=__version__
)

# Статические файлы
static_path = _BASE_DIR / "web" / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# === Pydantic модели ===

class PLCResponse(BaseModel):
    id: int
    name: str
    plc_type: str  # siemens_s7 или allen_bradley
    ip_address: str
    tcp_port: int
    rack: int
    slot: int
    slot_ab: int = 0  # Для Allen-Bradley
    is_active: bool
    tag_count: int
    connection_status: str = "unknown"  # connected, disconnected, stopped


class TagResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    # Siemens S7 addressing (nullable for AB)
    memory_area: str = "DB"  # DB, I, Q, M
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: int = 0
    data_type: str
    # Allen-Bradley addressing
    ab_tag_name: Optional[str] = None
    poll_interval_ms: int
    latest_value: Optional[float]
    latest_time: Optional[str]


class TrendPointResponse(BaseModel):
    timestamp: str
    value: float


class StatisticsResponse(BaseModel):
    min: Optional[float]
    max: Optional[float]
    avg: Optional[float]
    count: int
    start_time: str
    end_time: str


class SystemStatusResponse(BaseModel):
    version: str
    plc_count: int
    tag_count: int
    trend_count: int
    last_update: Optional[str]
    collector_running: bool = False
    connection_status: str = "unknown"  # connected, disconnected, error
    plc_errors: Dict[str, str] = {}  # plc_name -> error message


# Размеры типов данных S7 (в байтах)
DATA_TYPE_SIZES = {
    'bool': 1,
    'int': 2,
    'word': 2,
    'dint': 4,
    'dword': 4,
    'real': 4,
    'string': 256,  # По умолчанию для строк
}


def get_data_size(data_type: str) -> int:
    """Получить размер данных по типу"""
    return DATA_TYPE_SIZES.get(data_type.lower(), 4)


class TagCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    # Siemens S7 addressing (optional for AB)
    memory_area: str = "DB"  # DB, I, Q, M (область памяти S7)
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: int = 0  # Номер бита (0-7, только для BOOL)
    data_type: str = "real"  # int, dint, real, bool, word
    data_size: Optional[int] = None  # Опционально - автоопределение по типу
    # Allen-Bradley addressing
    ab_tag_name: Optional[str] = None  # Имя тега в AB ПЛК
    poll_interval_ms: int = 1000
    plc_id: Optional[int] = None  # Если не указан, берём первый активный ПЛК
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Tag name cannot be empty')
        if len(v) > 100:
            raise ValueError('Tag name too long (max 100 characters)')
        return v
    
    @field_validator('memory_area')
    @classmethod
    def validate_memory_area(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in ['DB', 'I', 'Q', 'M', 'T', 'C']:
            raise ValueError('Memory area must be one of: DB, I, Q, M, T, C')
        return v
    
    @field_validator('db_number')
    @classmethod
    def validate_db_number(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 65535:
            raise ValueError('DB number must be between 1 and 65535')
        return v
    
    @field_validator('start_address')
    @classmethod
    def validate_start_address(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 0 <= v <= 65535:
            raise ValueError('Start address must be between 0 and 65535')
        return v
    
    @field_validator('data_type')
    @classmethod
    def validate_data_type(cls, v: str) -> str:
        v = v.lower().strip()
        valid_types = {'int', 'dint', 'real', 'bool', 'word', 'dword', 'string'}
        if v not in valid_types:
            raise ValueError(f'Invalid data type. Must be one of: {", ".join(valid_types)}')
        return v
    
    @field_validator('poll_interval_ms')
    @classmethod
    def validate_poll_interval(cls, v: int) -> int:
        if not 100 <= v <= 60000:
            raise ValueError('Poll interval must be between 100ms and 60000ms')
        return v
    
    @field_validator('bit_number')
    @classmethod
    def validate_bit_number(cls, v: int) -> int:
        if not 0 <= v <= 7:
            raise ValueError('Bit number must be between 0 and 7')
        return v
    
    @field_validator('ab_tag_name')
    @classmethod
    def validate_ab_tag_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError('AB tag name too long (max 255 characters)')
        return v


class TagCreateResponse(BaseModel):
    id: int
    name: str
    message: str


class TagUpdateRequest(BaseModel):
    """Запрос на обновление тега"""
    name: Optional[str] = None
    description: Optional[str] = None
    # Siemens S7 addressing
    memory_area: Optional[str] = None  # DB, I, Q, M
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: Optional[int] = None
    data_type: Optional[str] = None
    # Allen-Bradley addressing
    ab_tag_name: Optional[str] = None
    poll_interval_ms: Optional[int] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('Tag name cannot be empty')
            if len(v) > 100:
                raise ValueError('Tag name too long (max 100 characters)')
        return v
    
    @field_validator('memory_area')
    @classmethod
    def validate_memory_area(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.upper().strip()
            if v not in ['DB', 'I', 'Q', 'M', 'T', 'C']:
                raise ValueError('Memory area must be one of: DB, I, Q, M, T, C')
        return v
    
    @field_validator('db_number')
    @classmethod
    def validate_db_number(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 65535:
            raise ValueError('DB number must be between 1 and 65535')
        return v
    
    @field_validator('start_address')
    @classmethod
    def validate_start_address(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 0 <= v <= 65535:
            raise ValueError('Start address must be between 0 and 65535')
        return v
    
    @field_validator('data_type')
    @classmethod
    def validate_data_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.lower().strip()
            valid_types = {'int', 'dint', 'real', 'bool', 'word', 'dword', 'string'}
            if v not in valid_types:
                raise ValueError(f'Invalid data type. Must be one of: {", ".join(valid_types)}')
        return v
    
    @field_validator('poll_interval_ms')
    @classmethod
    def validate_poll_interval(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 100 <= v <= 60000:
            raise ValueError('Poll interval must be between 100ms and 60000ms')
        return v
    
    @field_validator('bit_number')
    @classmethod
    def validate_bit_number(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 0 <= v <= 7:
            raise ValueError('Bit number must be between 0 and 7')
        return v


class PLCCreateRequest(BaseModel):
    name: str
    plc_type: str = PLC_TYPE_SIEMENS_S7  # siemens_s7 или allen_bradley
    ip_address: str
    tcp_port: int = 102
    # Siemens S7 specific
    rack: int = 0
    slot: int = 2
    # Allen-Bradley specific
    slot_ab: int = 0
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Name cannot be empty')
        if len(v) > 100:
            raise ValueError('Name too long (max 100 characters)')
        if not re.match(r'^[\w\s\-\.]+$', v):
            raise ValueError('Name contains invalid characters')
        return v
    
    @field_validator('plc_type')
    @classmethod
    def validate_plc_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in PLC_TYPES:
            raise ValueError(f'Invalid PLC type. Must be one of: {", ".join(PLC_TYPES)}')
        return v
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip(cls, v: str) -> str:
        v = v.strip()
        # IPv4 validation
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(pattern, v):
            raise ValueError(f'Invalid IP address: {v}')
        return v
    
    @field_validator('tcp_port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v
    
    @field_validator('rack')
    @classmethod
    def validate_rack(cls, v: int) -> int:
        if not 0 <= v <= 7:
            raise ValueError('Rack must be between 0 and 7')
        return v
    
    @field_validator('slot')
    @classmethod
    def validate_slot(cls, v: int) -> int:
        if not 0 <= v <= 31:
            raise ValueError('Slot must be between 0 and 31')
        return v
    
    @field_validator('slot_ab')
    @classmethod
    def validate_slot_ab(cls, v: int) -> int:
        if not 0 <= v <= 16:
            raise ValueError('AB Slot must be between 0 and 16')
        return v


class PLCCreateResponse(BaseModel):
    id: int
    name: str
    message: str


# === Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница"""
    template_path = _BASE_DIR / "web" / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("<h1>Trends</h1><p>UI not found. Check installation.</p>")


@app.get("/api/status", response_model=SystemStatusResponse)
async def get_status():
    """Статус системы"""
    with get_session() as session:
        plc_count = session.query(PLC).filter(PLC.is_active == True).count()
        tag_count = session.query(Tag).filter(Tag.is_active == True).count()
        trend_count = session.query(TrendData).count()
        
        last = session.query(TrendData).order_by(TrendData.timestamp.desc()).first()
        last_update = last.timestamp.isoformat() if last else None
        
        # Определяем статус подключения
        if collector_status.running:
            if collector_status.connected:
                conn_status = "connected"
            else:
                conn_status = "disconnected"
        else:
            conn_status = "stopped"
        
        # Получаем ошибки PLC с именами
        plc_errors = {}
        errors_by_id = collector_status.get_all_errors()
        if errors_by_id:
            plcs = session.query(PLC).filter(PLC.id.in_(errors_by_id.keys())).all()
            plc_names = {p.id: p.name for p in plcs}
            for plc_id, error in errors_by_id.items():
                plc_name = plc_names.get(plc_id, f"PLC #{plc_id}")
                plc_errors[plc_name] = error
        
        return SystemStatusResponse(
            version=__version__,
            plc_count=plc_count,
            tag_count=tag_count,
            trend_count=trend_count,
            last_update=last_update,
            collector_running=collector_status.running,
            connection_status=conn_status,
            plc_errors=plc_errors
        )


@app.get("/api/plcs", response_model=List[PLCResponse])
async def list_plcs():
    """Список всех ПЛК (активных и неактивных)"""
    with get_session() as session:
        plcs = session.query(PLC).all()
        
        result = []
        for plc in plcs:
            tag_count = session.query(Tag).filter(
                Tag.plc_id == plc.id, 
                Tag.is_active == True
            ).count()
            
            # Определяем статус подключения для этого PLC
            if not plc.is_active:
                conn_status = "stopped"
            elif collector_status.running:
                plc_connected = collector_status.get_plc_status(plc.id)
                if plc_connected is True:
                    conn_status = "connected"
                elif plc_connected is False:
                    conn_status = "disconnected"
                else:
                    conn_status = "unknown"
            else:
                conn_status = "stopped"
            
            result.append(PLCResponse(
                id=plc.id,
                name=plc.name,
                plc_type=getattr(plc, 'plc_type', PLC_TYPE_SIEMENS_S7),
                ip_address=plc.ip_address,
                tcp_port=plc.tcp_port,
                rack=plc.rack,
                slot=plc.slot,
                slot_ab=getattr(plc, 'slot_ab', 0),
                is_active=plc.is_active,
                tag_count=tag_count,
                connection_status=conn_status
            ))
        
        return result


@app.post("/api/plcs", response_model=PLCCreateResponse)
async def create_plc(request: PLCCreateRequest):
    """Создание нового ПЛК"""
    with get_session() as session:
        # Проверяем уникальность имени
        existing = session.query(PLC).filter(PLC.name == request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"PLC '{request.name}' already exists")
        
        # Установка порта по умолчанию в зависимости от типа
        tcp_port = request.tcp_port
        if tcp_port == 102 and request.plc_type == PLC_TYPE_ALLEN_BRADLEY:
            tcp_port = 44818  # Порт EtherNet/IP по умолчанию
        
        plc = PLC(
            name=request.name,
            plc_type=request.plc_type,
            ip_address=request.ip_address,
            tcp_port=tcp_port,
            rack=request.rack,
            slot=request.slot,
            slot_ab=request.slot_ab,
            is_active=True
        )
        session.add(plc)
        session.flush()
        
        # Автоматический перезапуск коллектора
        collector_status.request_restart()
        
        return PLCCreateResponse(
            id=plc.id,
            name=plc.name,
            message=f"PLC '{plc.name}' ({request.plc_type}) created successfully"
        )


@app.put("/api/plcs/{plc_id}")
async def update_plc(plc_id: int, request: PLCCreateRequest):
    """Обновление ПЛК"""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")
        
        # Проверяем уникальность имени (если изменилось)
        if request.name != plc.name:
            existing = session.query(PLC).filter(PLC.name == request.name).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"PLC '{request.name}' already exists")
        
        plc.name = request.name
        plc.plc_type = request.plc_type
        plc.ip_address = request.ip_address
        plc.tcp_port = request.tcp_port
        plc.rack = request.rack
        plc.slot = request.slot
        plc.slot_ab = request.slot_ab
        
        # Автоматический перезапуск коллектора
        collector_status.request_restart()
        
        return {"message": f"PLC '{plc.name}' updated", "id": plc_id}


@app.delete("/api/plcs/{plc_id}")
async def delete_plc(plc_id: int):
    """Полное удаление ПЛК из базы данных"""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")
        
        plc_name = plc.name
        
        # Удаляем все теги этого ПЛК
        session.query(Tag).filter(Tag.plc_id == plc_id).delete()
        
        # Удаляем сам ПЛК
        session.delete(plc)
        
        # Автоматический перезапуск коллектора
        collector_status.request_restart()
        
        return {"message": f"PLC '{plc_name}' deleted permanently", "id": plc_id}


@app.put("/api/plcs/{plc_id}/toggle")
async def toggle_plc(plc_id: int):
    """Включение/выключение опроса ПЛК"""
    plc_name = ""
    new_is_active = False
    
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")
        
        # Переключаем активность
        plc.is_active = not plc.is_active
        new_is_active = plc.is_active
        plc_name = plc.name
        
        # Commit changes before restart
        session.commit()
    
    # Restart collector AFTER database commit
    collector_status.request_restart()
    
    # Очищаем ошибку при деактивации
    if not new_is_active:
        with collector_status._lock:
            collector_status._plc_errors.pop(plc_id, None)
            collector_status._plc_statuses.pop(plc_id, None)
    
    new_status = "enabled" if new_is_active else "disabled"
    return {
        "message": f"PLC '{plc_name}' polling {new_status}",
        "id": plc_id,
        "is_active": new_is_active
    }


@app.post("/api/collector/restart")
async def restart_collector():
    """Запрос на перезапуск коллектора"""
    collector_status.request_restart()
    return {"message": "Restart requested", "status": "pending"}


@app.get("/api/plcs/{plc_id}/browse")
async def browse_plc(plc_id: int, program: str = None):
    """
    Browse PLC - получить список тегов/блоков из ПЛК.
    - Siemens S7: возвращает список Data Blocks и области памяти
    - Allen-Bradley: возвращает полный список тегов из ПЛК
    
    Args:
        program: (только для AB) '*' для всех тегов, имя программы, или None для controller-scope
    """
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")
        
        plc_type = getattr(plc, 'plc_type', PLC_TYPE_SIEMENS_S7)
        
        if plc_type == PLC_TYPE_ALLEN_BRADLEY:
            return await _browse_allen_bradley(plc, program)
        else:
            return await _browse_siemens_s7(plc)


async def _browse_siemens_s7(plc):
    """Browse Siemens S7 PLC - get Data Blocks"""
    try:
        import snap7
        from snap7.type import Block
        
        client = snap7.client.Client()
        client.connect(plc.ip_address, plc.rack, plc.slot, plc.tcp_port)
        
        if not client.get_connected():
            raise HTTPException(status_code=503, detail="Cannot connect to PLC")
        
        # Получаем общую информацию о блоках
        blocks_info = client.list_blocks()
        
        # Получаем список DB
        db_list = []
        for db_num in range(1, 101):
            try:
                info = client.get_block_info(Block.DB, db_num)
                db_list.append({
                    "db_number": db_num,
                    "size": info.MC7Size,
                    "load_size": info.LoadSize if hasattr(info, 'LoadSize') else None
                })
            except Exception:
                pass  # DB doesn't exist
        
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
            "tags": []  # S7 не предоставляет имена тегов
        }
        
    except ImportError:
        raise HTTPException(status_code=500, detail="snap7 library not available")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PLC browse failed: {str(e)}")


async def _browse_allen_bradley(plc, program: str = None):
    """Browse Allen-Bradley PLC - get full tag list"""
    from app.services.runtime_config import runtime_config
    
    # В режиме симуляции возвращаем фейковые теги
    if runtime_config.simulate_mode:
        return _get_simulated_ab_tags(plc)
    
    try:
        from pycomm3 import LogixDriver
        
        # Формируем путь подключения
        slot = getattr(plc, 'slot_ab', 0) or 0
        if slot > 0:
            path = f"{plc.ip_address}/{slot}"
        else:
            path = plc.ip_address
        
        with LogixDriver(path) as driver:
            # Получаем список тегов
            # program='*' - все теги, None - только controller-scope
            tag_list = driver.get_tag_list(program=program or '*')
            
            # Форматируем теги для ответа
            tags = []
            for tag_info in tag_list:
                tag_data = {
                    "tag_name": tag_info.get('tag_name', ''),
                    "data_type": str(tag_info.get('data_type', 'UNKNOWN')),
                    "data_type_name": tag_info.get('data_type_name', ''),
                    "dim": tag_info.get('dim', 0),  # размерность массива
                    "external_access": tag_info.get('external_access', ''),
                }
                
                # Добавляем размеры массива если есть
                if tag_info.get('dimensions'):
                    tag_data['dimensions'] = tag_info['dimensions']
                
                tags.append(tag_data)
            
            return {
                "plc_id": plc.id,
                "plc_name": plc.name,
                "plc_type": "allen_bradley",
                "connected": True,
                "tag_count": len(tags),
                "tags": tags,
                "data_blocks": [],
                "memory_areas": []
            }
            
    except ImportError:
        raise HTTPException(status_code=500, detail="pycomm3 library not installed. Run: pip install pycomm3")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PLC browse failed: {str(e)}")


def _get_simulated_ab_tags(plc):
    """Возвращает симулированные теги для Allen-Bradley PLC"""
    # Симулированные теги с разными типами данных
    simulated_tags = [
        # Process variables
        {"tag_name": "Temperature", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Pressure", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "FlowRate", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Level", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "Speed", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        
        # Setpoints
        {"tag_name": "TempSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "PressureSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        {"tag_name": "SpeedSetpoint", "data_type": "REAL", "data_type_name": "REAL", "dim": 0},
        
        # Counters and integers
        {"tag_name": "ProductCount", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "BatchNumber", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "CycleCount", "data_type": "DINT", "data_type_name": "DINT", "dim": 0},
        {"tag_name": "ErrorCode", "data_type": "INT", "data_type_name": "INT", "dim": 0},
        {"tag_name": "Status", "data_type": "INT", "data_type_name": "INT", "dim": 0},
        
        # Boolean tags
        {"tag_name": "Motor_Running", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "Pump_On", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "Alarm_Active", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "SystemReady", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        {"tag_name": "EmergencyStop", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 0},
        
        # Arrays
        {"tag_name": "TempArray", "data_type": "REAL", "data_type_name": "REAL", "dim": 1, "dimensions": [10]},
        {"tag_name": "IOStatus", "data_type": "BOOL", "data_type_name": "BOOL", "dim": 1, "dimensions": [32]},
        
        # Program-scoped tags
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
        "memory_areas": []
    }


@app.get("/api/tags", response_model=List[TagResponse])
async def list_tags(plc_id: Optional[int] = None):
    """Список тегов с последними значениями (оптимизировано)"""
    with get_session() as session:
        query = session.query(Tag).filter(Tag.is_active == True)
        
        if plc_id:
            query = query.filter(Tag.plc_id == plc_id)
        
        tags = query.all()
        
        # Получаем все последние значения одним запросом (решение N+1)
        tag_ids = [tag.id for tag in tags]
        latest_values = get_latest_values_batch(tag_ids)
        
        result = []
        for tag in tags:
            latest = latest_values.get(tag.id)
            
            result.append(TagResponse(
                id=tag.id,
                name=tag.name,
                description=tag.description,
                memory_area=getattr(tag, 'memory_area', None) or "DB",
                db_number=tag.db_number,
                start_address=tag.start_address,
                bit_number=tag.bit_number or 0,
                data_type=tag.data_type,
                ab_tag_name=getattr(tag, 'ab_tag_name', None),
                poll_interval_ms=tag.poll_interval_ms,
                latest_value=latest[1] if latest else None,
                latest_time=latest[0].isoformat() if latest else None
            ))
        
        return result


@app.get("/api/tags/{tag_id}/trend", response_model=List[TrendPointResponse])
async def get_tag_trend(
    tag_id: int,
    minutes: int = Query(default=60, ge=1, le=1440, description="Период в минутах")
):
    """Данные тренда за период"""
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)
    
    data = get_trend_data(tag_id, start_time, end_time, limit=5000)
    
    return [
        TrendPointResponse(
            timestamp=ts.isoformat(),
            value=round(val, 2)
        )
        for ts, val in data
    ]


class TagTrendResponse(BaseModel):
    tag_id: int
    tag_name: str
    data: List[TrendPointResponse]


@app.get("/api/trends", response_model=List[TagTrendResponse])
async def get_all_trends(
    plc_id: Optional[int] = None,
    minutes: int = Query(default=60, ge=1, le=1440, description="Период в минутах")
):
    """Данные трендов для всех тегов (для отображения на одном графике)"""
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)
    
    with get_session() as session:
        query = session.query(Tag).filter(Tag.is_active == True)
        if plc_id:
            query = query.filter(Tag.plc_id == plc_id)
        tags = query.all()
        
        result = []
        for tag in tags:
            data = get_trend_data(tag.id, start_time, end_time, limit=5000)
            result.append(TagTrendResponse(
                tag_id=tag.id,
                tag_name=tag.name,
                data=[
                    TrendPointResponse(timestamp=ts.isoformat(), value=round(val, 2))
                    for ts, val in data
                ]
            ))
        
        return result


@app.get("/api/tags/{tag_id}/statistics", response_model=StatisticsResponse)
async def get_tag_statistics(
    tag_id: int,
    minutes: int = Query(default=60, ge=1, le=1440)
):
    """Статистика по тегу"""
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=minutes)
    
    stats = get_statistics(tag_id, start_time, end_time)
    
    return StatisticsResponse(**stats)


@app.get("/api/tags/{tag_id}/latest")
async def get_tag_latest(tag_id: int):
    """Последнее значение тега"""
    result = get_latest_value(tag_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="No data found")
    
    return {
        "timestamp": result[0].isoformat(),
        "value": round(result[1], 2)
    }


@app.post("/api/tags", response_model=TagCreateResponse)
async def create_tag(request: TagCreateRequest):
    """Создание нового тега"""
    with get_session() as session:
        # Определяем PLC
        if request.plc_id:
            plc = session.query(PLC).filter(PLC.id == request.plc_id).first()
        else:
            plc = session.query(PLC).filter(PLC.is_active == True).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="No active PLC found")
        
        plc_type = getattr(plc, 'plc_type', PLC_TYPE_SIEMENS_S7)
        
        # Валидация в зависимости от типа ПЛК
        if plc_type == PLC_TYPE_ALLEN_BRADLEY:
            # Для Allen-Bradley требуется имя тега
            if not request.ab_tag_name:
                raise HTTPException(status_code=400, detail="AB tag name is required for Allen-Bradley PLC")
            
            # Проверяем уникальность AB тега
            existing = session.query(Tag).filter(
                Tag.plc_id == plc.id,
                Tag.ab_tag_name == request.ab_tag_name
            ).first()
            
            if existing and existing.is_active:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tag '{request.ab_tag_name}' already exists"
                )
            
            address_str = request.ab_tag_name
        else:
            # Для Siemens S7 требуется адрес
            memory_area = request.memory_area or "DB"
            
            # Для DB требуется db_number, для I/Q/M - нет
            if memory_area == "DB":
                if request.db_number is None or request.start_address is None:
                    raise HTTPException(status_code=400, detail="DB number and start address are required for DB area")
            else:
                if request.start_address is None:
                    raise HTTPException(status_code=400, detail="Start address is required for Siemens S7 PLC")
            
            # Проверяем уникальность адреса S7
            query = session.query(Tag).filter(
                Tag.plc_id == plc.id,
                Tag.memory_area == memory_area,
                Tag.start_address == request.start_address
            )
            
            if memory_area == "DB":
                query = query.filter(Tag.db_number == request.db_number)
            
            if request.data_type == 'bool':
                query = query.filter(Tag.bit_number == request.bit_number)
                if memory_area == "DB":
                    address_str = f"DB{request.db_number}.DBX{request.start_address}.{request.bit_number}"
                else:
                    address_str = f"{memory_area}{request.start_address}.{request.bit_number}"
            else:
                if memory_area == "DB":
                    address_str = f"DB{request.db_number}.{request.start_address}"
                else:
                    address_str = f"{memory_area}{request.start_address}"
            
            existing = query.first()
            
            if existing and existing.is_active:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tag at {address_str} already exists"
                )
        
        # Реактивация существующего тега
        if existing and not existing.is_active:
            existing.name = request.name
            existing.description = request.description
            existing.memory_area = request.memory_area or "DB"
            existing.bit_number = request.bit_number if request.data_type == 'bool' else 0
            existing.data_type = request.data_type
            existing.data_size = get_data_size(request.data_type)
            existing.ab_tag_name = request.ab_tag_name
            existing.poll_interval_ms = request.poll_interval_ms
            existing.is_active = True
            
            collector_status.request_restart()
            
            return TagCreateResponse(
                id=existing.id,
                name=existing.name,
                message="Tag reactivated"
            )
        
        # Создаём новый тег
        tag = Tag(
            plc_id=plc.id,
            name=request.name,
            description=request.description,
            memory_area=request.memory_area or "DB",
            db_number=request.db_number if request.memory_area == "DB" else None,
            start_address=request.start_address,
            bit_number=request.bit_number if request.data_type == 'bool' else 0,
            data_type=request.data_type,
            data_size=get_data_size(request.data_type) if request.start_address is not None else None,
            ab_tag_name=request.ab_tag_name,
            poll_interval_ms=request.poll_interval_ms,
            is_active=True
        )
        session.add(tag)
        session.flush()
        
        collector_status.request_restart()
        
        return TagCreateResponse(
            id=tag.id,
            name=tag.name,
            message=f"Tag '{tag.name}' created successfully"
        )


@app.put("/api/tags/{tag_id}")
async def update_tag(tag_id: int, request: TagUpdateRequest):
    """Обновление существующего тега"""
    with get_session() as session:
        tag = session.query(Tag).filter(Tag.id == tag_id).first()
        
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        # Получаем тип ПЛК
        plc = session.query(PLC).filter(PLC.id == tag.plc_id).first()
        plc_type = getattr(plc, 'plc_type', PLC_TYPE_SIEMENS_S7) if plc else PLC_TYPE_SIEMENS_S7
        
        # Обновляем только переданные поля
        if request.name is not None:
            tag.name = request.name
        
        if request.description is not None:
            tag.description = request.description
        
        if request.poll_interval_ms is not None:
            tag.poll_interval_ms = request.poll_interval_ms
        
        # Поля для Siemens S7
        if plc_type == PLC_TYPE_SIEMENS_S7:
            if request.memory_area is not None:
                tag.memory_area = request.memory_area
                # Если меняем на не-DB область, обнуляем db_number
                if request.memory_area != "DB":
                    tag.db_number = None
            
            if request.db_number is not None:
                tag.db_number = request.db_number
            
            if request.start_address is not None:
                tag.start_address = request.start_address
            
            if request.data_type is not None:
                tag.data_type = request.data_type
                tag.data_size = get_data_size(request.data_type)
                # Обновляем bit_number только для bool
                if request.data_type == 'bool' and request.bit_number is not None:
                    tag.bit_number = request.bit_number
                elif request.data_type != 'bool':
                    tag.bit_number = 0
            elif request.bit_number is not None and tag.data_type == 'bool':
                tag.bit_number = request.bit_number
        
        # Поля для Allen-Bradley
        if plc_type == PLC_TYPE_ALLEN_BRADLEY:
            if request.ab_tag_name is not None:
                tag.ab_tag_name = request.ab_tag_name
            
            if request.data_type is not None:
                tag.data_type = request.data_type
        
        # Автоматический перезапуск коллектора
        collector_status.request_restart()
        
        return {"message": f"Tag '{tag.name}' updated", "id": tag_id}


@app.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: int):
    """Полное удаление тега и его данных из БД"""
    with get_session() as session:
        tag = session.query(Tag).filter(Tag.id == tag_id).first()
        
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        tag_name = tag.name
        
        # Удаляем все данные тренда для этого тега
        deleted_trends = session.query(TrendData).filter(TrendData.tag_id == tag_id).delete()
        
        # Удаляем сам тег
        session.delete(tag)
        
        # Автоматический перезапуск коллектора
        collector_status.request_restart()
        
        return {"message": f"Tag '{tag_name}' and {deleted_trends} trend records deleted", "id": tag_id}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Запуск сервера"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()

