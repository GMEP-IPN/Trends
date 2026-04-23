"""
Сервис операций с тегами.
Инкапсулирует логику выбора ПЛК, проверки уникальности адресов S7/AB,
реактивации существующих тегов и форматирования адресов в сообщениях ошибок.
"""
from typing import Dict, Any, Optional, Tuple

from fastapi import HTTPException

from app.api.schemas import TagCreateRequest, TagUpdateRequest
from app.config.constants import get_data_size
from app.services.collector_status import collector_status
from app.storage import get_session, PLC, Tag, TrendData
from app.storage.models import PLC_TYPE_ALLEN_BRADLEY, PLC_TYPE_SIEMENS_S7


def _format_s7_address(memory_area: str, db_number: Optional[int], start_address: int,
                      data_type: str, bit_number: int) -> str:
    """Строка адреса S7 для сообщений об ошибках."""
    if data_type == "bool":
        if memory_area == "DB":
            return f"DB{db_number}.DBX{start_address}.{bit_number}"
        return f"{memory_area}{start_address}.{bit_number}"
    if memory_area == "DB":
        return f"DB{db_number}.{start_address}"
    return f"{memory_area}{start_address}"


def _find_target_plc(session, plc_id: Optional[int]) -> PLC:
    """Возвращает указанный PLC или первый активный. Иначе 404."""
    if plc_id:
        plc = session.query(PLC).filter(PLC.id == plc_id).first()
    else:
        plc = session.query(PLC).filter(PLC.is_active == True).first()
    if not plc:
        raise HTTPException(status_code=404, detail="No active PLC found")
    return plc


def _find_existing_ab_tag(session, plc_id: int, ab_tag_name: str) -> Optional[Tag]:
    return session.query(Tag).filter(
        Tag.plc_id == plc_id,
        Tag.ab_tag_name == ab_tag_name,
    ).first()


def _find_existing_s7_tag(session, plc_id: int, memory_area: str,
                          start_address: int, db_number: Optional[int],
                          data_type: str, bit_number: int) -> Optional[Tag]:
    query = session.query(Tag).filter(
        Tag.plc_id == plc_id,
        Tag.memory_area == memory_area,
        Tag.start_address == start_address,
    )
    if memory_area == "DB":
        query = query.filter(Tag.db_number == db_number)
    if data_type == "bool":
        query = query.filter(Tag.bit_number == bit_number)
    return query.first()


def _validate_ab_request(request: TagCreateRequest) -> None:
    if not request.ab_tag_name:
        raise HTTPException(
            status_code=400,
            detail="AB tag name is required for Allen-Bradley PLC",
        )


def _validate_s7_request(request: TagCreateRequest, memory_area: str) -> None:
    if memory_area == "DB":
        if request.db_number is None or request.start_address is None:
            raise HTTPException(
                status_code=400,
                detail="DB number and start address are required for DB area",
            )
    else:
        if request.start_address is None:
            raise HTTPException(
                status_code=400,
                detail="Start address is required for Siemens S7 PLC",
            )


def _reactivate_tag(tag: Tag, request: TagCreateRequest) -> Dict[str, Any]:
    tag.name = request.name
    tag.description = request.description
    tag.memory_area = request.memory_area or "DB"
    tag.bit_number = request.bit_number if request.data_type == "bool" else 0
    tag.data_type = request.data_type
    tag.data_size = get_data_size(request.data_type)
    tag.ab_tag_name = request.ab_tag_name
    tag.poll_interval_ms = request.poll_interval_ms
    tag.is_active = True

    collector_status.request_restart()
    return {"id": tag.id, "name": tag.name, "message": "Tag reactivated"}


def create_tag(request: TagCreateRequest) -> Dict[str, Any]:
    with get_session() as session:
        plc = _find_target_plc(session, request.plc_id)
        plc_type = getattr(plc, "plc_type", PLC_TYPE_SIEMENS_S7)

        existing: Optional[Tag] = None

        if plc_type == PLC_TYPE_ALLEN_BRADLEY:
            _validate_ab_request(request)
            existing = _find_existing_ab_tag(session, plc.id, request.ab_tag_name)
            if existing and existing.is_active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tag '{request.ab_tag_name}' already exists",
                )
        else:
            memory_area = request.memory_area or "DB"
            _validate_s7_request(request, memory_area)
            existing = _find_existing_s7_tag(
                session, plc.id, memory_area, request.start_address,
                request.db_number, request.data_type, request.bit_number,
            )
            if existing and existing.is_active:
                address_str = _format_s7_address(
                    memory_area, request.db_number, request.start_address,
                    request.data_type, request.bit_number,
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Tag at {address_str} already exists",
                )

        if existing and not existing.is_active:
            return _reactivate_tag(existing, request)

        tag = Tag(
            plc_id=plc.id,
            name=request.name,
            description=request.description,
            memory_area=request.memory_area or "DB",
            db_number=request.db_number if request.memory_area == "DB" else None,
            start_address=request.start_address,
            bit_number=request.bit_number if request.data_type == "bool" else 0,
            data_type=request.data_type,
            data_size=get_data_size(request.data_type) if request.start_address is not None else None,
            ab_tag_name=request.ab_tag_name,
            poll_interval_ms=request.poll_interval_ms,
            is_active=True,
        )
        session.add(tag)
        session.flush()

        collector_status.request_restart()
        return {
            "id": tag.id,
            "name": tag.name,
            "message": f"Tag '{tag.name}' created successfully",
        }


def update_tag(tag_id: int, request: TagUpdateRequest) -> Dict[str, Any]:
    with get_session() as session:
        tag = session.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")

        plc = session.query(PLC).filter(PLC.id == tag.plc_id).first()
        plc_type = getattr(plc, "plc_type", PLC_TYPE_SIEMENS_S7) if plc else PLC_TYPE_SIEMENS_S7

        # Общие поля
        if request.name is not None:
            tag.name = request.name
        if request.description is not None:
            tag.description = request.description
        if request.poll_interval_ms is not None:
            tag.poll_interval_ms = request.poll_interval_ms

        if plc_type == PLC_TYPE_SIEMENS_S7:
            _apply_s7_updates(tag, request)
        elif plc_type == PLC_TYPE_ALLEN_BRADLEY:
            if request.ab_tag_name is not None:
                tag.ab_tag_name = request.ab_tag_name
            if request.data_type is not None:
                tag.data_type = request.data_type

        collector_status.request_restart()
        return {"message": f"Tag '{tag.name}' updated", "id": tag_id}


def _apply_s7_updates(tag: Tag, request: TagUpdateRequest) -> None:
    if request.memory_area is not None:
        tag.memory_area = request.memory_area
        if request.memory_area != "DB":
            tag.db_number = None

    if request.db_number is not None:
        tag.db_number = request.db_number

    if request.start_address is not None:
        tag.start_address = request.start_address

    if request.data_type is not None:
        tag.data_type = request.data_type
        tag.data_size = get_data_size(request.data_type)
        if request.data_type == "bool" and request.bit_number is not None:
            tag.bit_number = request.bit_number
        elif request.data_type != "bool":
            tag.bit_number = 0
    elif request.bit_number is not None and tag.data_type == "bool":
        tag.bit_number = request.bit_number


def delete_tag(tag_id: int) -> Dict[str, Any]:
    with get_session() as session:
        tag = session.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")

        tag_name = tag.name
        deleted_trends = session.query(TrendData).filter(TrendData.tag_id == tag_id).delete()
        session.delete(tag)

        collector_status.request_restart()
        return {
            "message": f"Tag '{tag_name}' and {deleted_trends} trend records deleted",
            "id": tag_id,
        }
