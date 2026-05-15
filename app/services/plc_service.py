"""
Сервис операций с ПЛК — создание, обновление, удаление, toggle.
Инкапсулирует все DB-операции и нормализацию порта по типу ПЛК.
"""
from typing import Dict, Any, Optional

from fastapi import HTTPException

from app.api.schemas import PLCCreateRequest
from app.config.constants import ETHERNET_IP_DEFAULT_PORT, S7_DEFAULT_PORT
from app.services.collector_status import collector_status
from app.storage import get_session, PLC, Tag
from app.storage.models import PLC_TYPE_ALLEN_BRADLEY, PLC_TYPE_SIEMENS_S7


def _default_port_for_type(plc_type: str, requested_port: int) -> int:
    """Если пользователь оставил дефолтный S7-порт для AB PLC — подменяем на 44818."""
    if requested_port == S7_DEFAULT_PORT and plc_type == PLC_TYPE_ALLEN_BRADLEY:
        return ETHERNET_IP_DEFAULT_PORT
    return requested_port


def _resolve_connection_status(plc: PLC) -> str:
    """Строка статуса подключения для одного PLC, учитывая запущен ли коллектор."""
    if not plc.is_active:
        return "stopped"
    if not collector_status.running:
        return "stopped"
    plc_connected = collector_status.get_plc_status(plc.id)
    if plc_connected is True:
        return "connected"
    if plc_connected is False:
        return "disconnected"
    return "unknown"


def list_plcs(include_archived: bool = False) -> list[dict]:
    """Список ПЛК со счётчиком тегов и статусом подключения."""
    with get_session() as session:
        query = session.query(PLC)
        if not include_archived:
            query = query.filter(PLC.is_archived == False)
        plcs = query.all()
        result = []
        for plc in plcs:
            tag_count = session.query(Tag).filter(
                Tag.plc_id == plc.id,
                Tag.is_active == True,
            ).count()

            result.append({
                "id": plc.id,
                "name": plc.name,
                "plc_type": getattr(plc, "plc_type", PLC_TYPE_SIEMENS_S7),
                "ip_address": plc.ip_address,
                "tcp_port": plc.tcp_port,
                "rack": plc.rack,
                "slot": plc.slot,
                "slot_ab": getattr(plc, "slot_ab", 0),
                "is_active": plc.is_active,
                "is_archived": getattr(plc, "is_archived", False),
                "tag_count": tag_count,
                "connection_status": _resolve_connection_status(plc),
            })
        return result


def create_plc(request: PLCCreateRequest) -> Dict[str, Any]:
    with get_session() as session:
        existing = session.query(PLC).filter(PLC.name == request.name).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"PLC '{request.name}' already exists",
            )

        plc = PLC(
            name=request.name,
            plc_type=request.plc_type,
            ip_address=request.ip_address,
            tcp_port=_default_port_for_type(request.plc_type, request.tcp_port),
            rack=request.rack,
            slot=request.slot,
            slot_ab=request.slot_ab,
            is_active=True,
        )
        session.add(plc)
        session.flush()

        collector_status.request_restart()

        return {
            "id": plc.id,
            "name": plc.name,
            "message": f"PLC '{plc.name}' ({request.plc_type}) created successfully",
        }


def update_plc(plc_id: int, request: PLCCreateRequest) -> Dict[str, Any]:
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")

        if request.name != plc.name:
            existing = session.query(PLC).filter(PLC.name == request.name).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"PLC '{request.name}' already exists",
                )

        plc.name = request.name
        plc.plc_type = request.plc_type
        plc.ip_address = request.ip_address
        plc.tcp_port = request.tcp_port
        plc.rack = request.rack
        plc.slot = request.slot
        plc.slot_ab = request.slot_ab

        collector_status.request_restart()
        return {"message": f"PLC '{plc.name}' updated", "id": plc_id}


def delete_plc(plc_id: int) -> Dict[str, Any]:
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")

        plc_name = plc.name
        session.query(Tag).filter(Tag.plc_id == plc_id).delete()
        session.delete(plc)

        collector_status.request_restart()
        return {"message": f"PLC '{plc_name}' deleted permanently", "id": plc_id}


def toggle_plc(plc_id: int) -> Dict[str, Any]:
    """Переключает is_active; коммитит до перезапуска коллектора."""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")

        plc.is_active = not plc.is_active
        new_is_active = plc.is_active
        plc_name = plc.name
        session.commit()

    collector_status.request_restart()

    if not new_is_active:
        collector_status.remove_plc(plc_id)

    new_status = "enabled" if new_is_active else "disabled"
    return {
        "message": f"PLC '{plc_name}' polling {new_status}",
        "id": plc_id,
        "is_active": new_is_active,
    }


def archive_plc(plc_id: int) -> Dict[str, Any]:
    """Убирает ПЛК в архив: отключает опрос, скрывает из основного списка."""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")

        plc.is_archived = True
        plc.is_active = False
        plc_name = plc.name
        session.commit()

    collector_status.remove_plc(plc_id)
    collector_status.request_restart()
    return {"message": f"PLC '{plc_name}' archived", "id": plc_id}


def unarchive_plc(plc_id: int) -> Dict[str, Any]:
    """Возвращает ПЛК из архива (опрос остаётся выключенным — включить вручную)."""
    with get_session() as session:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
        if not plc:
            raise HTTPException(status_code=404, detail="PLC not found")

        plc.is_archived = False
        plc_name = plc.name
        session.commit()

    return {"message": f"PLC '{plc_name}' restored from archive", "id": plc_id}


def get_plc_by_id(plc_id: int) -> Optional[PLC]:
    """Вспомогательная функция — используется браузером тегов в API."""
    with get_session() as session:
        return session.query(PLC).filter(PLC.id == plc_id).first()
