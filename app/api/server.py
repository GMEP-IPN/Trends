"""
REST API сервер для Trends Collector.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from app.storage import get_session, PLC, Tag, TrendData
from app.services.trend_service import (
    get_trend_data, 
    get_latest_value, 
    get_statistics,
    get_all_tags
)

# Глобальный статус коллектора (обновляется из run.py)
collector_status = {
    "running": False,
    "connected": False,
    "last_error": None,
    "plc_name": None,
    "restart_requested": False
}

app = FastAPI(
    title="Trends Collector API",
    description="API для просмотра трендов с ПЛК",
    version="1.0.0"
)

# Статические файлы
static_path = Path(__file__).parent.parent.parent / "web" / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# === Pydantic модели ===

class PLCResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    tcp_port: int
    rack: int
    slot: int
    is_active: bool
    tag_count: int


class TagResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    db_number: int
    start_address: int
    data_type: str
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
    plc_count: int
    tag_count: int
    trend_count: int
    last_update: Optional[str]
    collector_running: bool = False
    connection_status: str = "unknown"  # connected, disconnected, error


class TagCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    db_number: int
    start_address: int
    data_type: str  # int, dint, real, bool, word
    data_size: int
    poll_interval_ms: int = 1000
    plc_id: Optional[int] = None  # Если не указан, берём первый активный ПЛК


class TagCreateResponse(BaseModel):
    id: int
    name: str
    message: str


class PLCCreateRequest(BaseModel):
    name: str
    ip_address: str
    tcp_port: int = 102
    rack: int = 0
    slot: int = 1


class PLCCreateResponse(BaseModel):
    id: int
    name: str
    message: str


# === Endpoints ===

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница"""
    template_path = Path(__file__).parent.parent.parent / "web" / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("<h1>Trends Collector</h1><p>UI not found</p>")


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
        if collector_status["running"]:
            if collector_status["connected"]:
                conn_status = "connected"
            else:
                conn_status = "disconnected"
        else:
            conn_status = "stopped"
        
        return SystemStatusResponse(
            plc_count=plc_count,
            tag_count=tag_count,
            trend_count=trend_count,
            last_update=last_update,
            collector_running=collector_status["running"],
            connection_status=conn_status
        )


@app.get("/api/plcs", response_model=List[PLCResponse])
async def list_plcs():
    """Список ПЛК"""
    with get_session() as session:
        plcs = session.query(PLC).filter(PLC.is_active == True).all()
        
        result = []
        for plc in plcs:
            tag_count = session.query(Tag).filter(
                Tag.plc_id == plc.id, 
                Tag.is_active == True
            ).count()
            
            result.append(PLCResponse(
                id=plc.id,
                name=plc.name,
                ip_address=plc.ip_address,
                tcp_port=plc.tcp_port,
                rack=plc.rack,
                slot=plc.slot,
                is_active=plc.is_active,
                tag_count=tag_count
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
        
        plc = PLC(
            name=request.name,
            ip_address=request.ip_address,
            tcp_port=request.tcp_port,
            rack=request.rack,
            slot=request.slot,
            is_active=True
        )
        session.add(plc)
        session.flush()
        
        # Автоматический перезапуск коллектора
        collector_status["restart_requested"] = True
        
        return PLCCreateResponse(
            id=plc.id,
            name=plc.name,
            message=f"PLC '{plc.name}' created successfully"
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
        plc.ip_address = request.ip_address
        plc.tcp_port = request.tcp_port
        plc.rack = request.rack
        plc.slot = request.slot
        
        # Автоматический перезапуск коллектора
        collector_status["restart_requested"] = True
        
        return {"message": f"PLC '{plc.name}' updated", "id": plc_id}


@app.delete("/api/plcs/{plc_id}")
async def delete_plc(plc_id: int):
    """Удаление ПЛК (деактивация)"""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")
        
        plc.is_active = False
        
        # Деактивируем все теги этого ПЛК
        session.query(Tag).filter(Tag.plc_id == plc_id).update({"is_active": False})
        
        # Автоматический перезапуск коллектора
        collector_status["restart_requested"] = True
        
        return {"message": f"PLC '{plc.name}' deleted", "id": plc_id}


@app.post("/api/collector/restart")
async def restart_collector():
    """Запрос на перезапуск коллектора"""
    collector_status["restart_requested"] = True
    return {"message": "Restart requested", "status": "pending"}


@app.get("/api/tags", response_model=List[TagResponse])
async def list_tags(plc_id: Optional[int] = None):
    """Список тегов с последними значениями"""
    with get_session() as session:
        query = session.query(Tag).filter(Tag.is_active == True)
        
        if plc_id:
            query = query.filter(Tag.plc_id == plc_id)
        
        tags = query.all()
        
        result = []
        for tag in tags:
            latest = get_latest_value(tag.id)
            
            result.append(TagResponse(
                id=tag.id,
                name=tag.name,
                description=tag.description,
                db_number=tag.db_number,
                start_address=tag.start_address,
                data_type=tag.data_type,
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
    
    data = get_trend_data(tag_id, start_time, end_time, limit=1000)
    
    return [
        TrendPointResponse(
            timestamp=ts.isoformat(),
            value=round(val, 2)
        )
        for ts, val in data
    ]


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
        
        # Проверяем уникальность адреса
        existing = session.query(Tag).filter(
            Tag.plc_id == plc.id,
            Tag.db_number == request.db_number,
            Tag.start_address == request.start_address
        ).first()
        
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Tag at DB{request.db_number}.{request.start_address} already exists"
                )
            else:
                # Реактивируем существующий тег
                existing.name = request.name
                existing.description = request.description
                existing.data_type = request.data_type
                existing.data_size = request.data_size
                existing.poll_interval_ms = request.poll_interval_ms
                existing.is_active = True
                
                # Автоматический перезапуск коллектора
                collector_status["restart_requested"] = True
                
                return TagCreateResponse(
                    id=existing.id,
                    name=existing.name,
                    message="Tag reactivated"
                )
        
        # Создаём тег
        tag = Tag(
            plc_id=plc.id,
            name=request.name,
            description=request.description,
            db_number=request.db_number,
            start_address=request.start_address,
            data_type=request.data_type,
            data_size=request.data_size,
            poll_interval_ms=request.poll_interval_ms,
            is_active=True
        )
        session.add(tag)
        session.flush()
        
        # Автоматический перезапуск коллектора
        collector_status["restart_requested"] = True
        
        return TagCreateResponse(
            id=tag.id,
            name=tag.name,
            message=f"Tag '{tag.name}' created successfully"
        )


@app.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: int):
    """Удаление тега (деактивация)"""
    with get_session() as session:
        tag = session.query(Tag).filter(Tag.id == tag_id).first()
        
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        
        tag.is_active = False
        
        # Автоматический перезапуск коллектора
        collector_status["restart_requested"] = True
        
        return {"message": f"Tag '{tag.name}' deleted", "id": tag_id}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Запуск сервера"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()

