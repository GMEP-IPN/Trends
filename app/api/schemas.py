"""
Pydantic-схемы для REST API.
Все валидаторы и нормализаторы сосредоточены здесь, чтобы server.py остался
тонким HTTP-слоем.
"""
import re
from typing import Optional, List, Dict

from pydantic import BaseModel, Field, field_validator

from app.config.constants import (
    MAX_NAME_LENGTH,
    MAX_AB_TAG_NAME_LENGTH,
    DB_NUMBER_MIN,
    DB_NUMBER_MAX,
    START_ADDRESS_MIN,
    START_ADDRESS_MAX,
    BIT_NUMBER_MIN,
    BIT_NUMBER_MAX,
    RACK_MIN,
    RACK_MAX,
    SLOT_MIN,
    SLOT_MAX,
    AB_SLOT_MIN,
    AB_SLOT_MAX,
    TCP_PORT_MIN,
    TCP_PORT_MAX,
    POLL_INTERVAL_MIN_MS,
    POLL_INTERVAL_MAX_MS,
    DEFAULT_POLL_INTERVAL_MS,
    S7_MEMORY_AREAS,
    VALID_DATA_TYPES,
    S7_DEFAULT_PORT,
)
from app.storage.models import PLC_TYPE_SIEMENS_S7, PLC_TYPES


_IP_V4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)
_NAME_PATTERN = re.compile(r"^[\w\s\-\.]+$")


# --- Нормализаторы (чистые функции, переиспользуются валидаторами) ---

def _normalize_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Name cannot be empty")
    if len(v) > MAX_NAME_LENGTH:
        raise ValueError(f"Name too long (max {MAX_NAME_LENGTH} characters)")
    return v


def _normalize_memory_area(v: str) -> str:
    v = v.upper().strip()
    if v not in S7_MEMORY_AREAS:
        raise ValueError(f"Memory area must be one of: {', '.join(S7_MEMORY_AREAS)}")
    return v


def _normalize_data_type(v: str) -> str:
    v = v.lower().strip()
    if v not in VALID_DATA_TYPES:
        raise ValueError(
            f'Invalid data type. Must be one of: {", ".join(sorted(VALID_DATA_TYPES))}'
        )
    return v


def _validate_range(v: int, lo: int, hi: int, field_name: str) -> int:
    if not lo <= v <= hi:
        raise ValueError(f"{field_name} must be between {lo} and {hi}")
    return v


def _normalize_ab_tag_name(v: str) -> str:
    v = v.strip()
    if len(v) > MAX_AB_TAG_NAME_LENGTH:
        raise ValueError(f"AB tag name too long (max {MAX_AB_TAG_NAME_LENGTH} characters)")
    return v


# --- Response models ---

class PLCResponse(BaseModel):
    id: int
    name: str
    plc_type: str
    ip_address: str
    tcp_port: int
    rack: int
    slot: int
    slot_ab: int = 0
    is_active: bool
    tag_count: int
    connection_status: str = "unknown"


class TagResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    memory_area: str = "DB"
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: int = 0
    data_type: str
    ab_tag_name: Optional[str] = None
    poll_interval_ms: int
    latest_value: Optional[float]
    latest_time: Optional[str]


class TrendPointResponse(BaseModel):
    timestamp: str
    value: float


class TagTrendResponse(BaseModel):
    tag_id: int
    tag_name: str
    data: List[TrendPointResponse]


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
    connection_status: str = "unknown"
    plc_errors: Dict[str, str] = {}


class TagCreateResponse(BaseModel):
    id: int
    name: str
    message: str


class PLCCreateResponse(BaseModel):
    id: int
    name: str
    message: str


# --- Request models ---

class TagCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    # Siemens S7 addressing
    memory_area: str = "DB"
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: int = 0
    data_type: str = "real"
    data_size: Optional[int] = None
    # Allen-Bradley addressing
    ab_tag_name: Optional[str] = None
    poll_interval_ms: int = DEFAULT_POLL_INTERVAL_MS
    plc_id: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _normalize_name(v)

    @field_validator("memory_area")
    @classmethod
    def _v_memory_area(cls, v: str) -> str:
        return _normalize_memory_area(v)

    @field_validator("db_number")
    @classmethod
    def _v_db_number(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, DB_NUMBER_MIN, DB_NUMBER_MAX, "DB number")

    @field_validator("start_address")
    @classmethod
    def _v_start_address(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, START_ADDRESS_MIN, START_ADDRESS_MAX, "Start address")

    @field_validator("data_type")
    @classmethod
    def _v_data_type(cls, v: str) -> str:
        return _normalize_data_type(v)

    @field_validator("poll_interval_ms")
    @classmethod
    def _v_poll_interval(cls, v: int) -> int:
        return _validate_range(v, POLL_INTERVAL_MIN_MS, POLL_INTERVAL_MAX_MS, "Poll interval")

    @field_validator("bit_number")
    @classmethod
    def _v_bit_number(cls, v: int) -> int:
        return _validate_range(v, BIT_NUMBER_MIN, BIT_NUMBER_MAX, "Bit number")

    @field_validator("ab_tag_name")
    @classmethod
    def _v_ab_tag_name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_ab_tag_name(v)


class TagUpdateRequest(BaseModel):
    """Все поля опциональны — обновляем только переданное."""
    name: Optional[str] = None
    description: Optional[str] = None
    memory_area: Optional[str] = None
    db_number: Optional[int] = None
    start_address: Optional[int] = None
    bit_number: Optional[int] = None
    data_type: Optional[str] = None
    ab_tag_name: Optional[str] = None
    poll_interval_ms: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_name(v)

    @field_validator("memory_area")
    @classmethod
    def _v_memory_area(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_memory_area(v)

    @field_validator("db_number")
    @classmethod
    def _v_db_number(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, DB_NUMBER_MIN, DB_NUMBER_MAX, "DB number")

    @field_validator("start_address")
    @classmethod
    def _v_start_address(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, START_ADDRESS_MIN, START_ADDRESS_MAX, "Start address")

    @field_validator("data_type")
    @classmethod
    def _v_data_type(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _normalize_data_type(v)

    @field_validator("poll_interval_ms")
    @classmethod
    def _v_poll_interval(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, POLL_INTERVAL_MIN_MS, POLL_INTERVAL_MAX_MS, "Poll interval")

    @field_validator("bit_number")
    @classmethod
    def _v_bit_number(cls, v: Optional[int]) -> Optional[int]:
        return None if v is None else _validate_range(v, BIT_NUMBER_MIN, BIT_NUMBER_MAX, "Bit number")


class PLCCreateRequest(BaseModel):
    name: str
    plc_type: str = PLC_TYPE_SIEMENS_S7
    ip_address: str
    tcp_port: int = S7_DEFAULT_PORT
    rack: int = 0
    slot: int = 1
    slot_ab: int = 0

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        v = _normalize_name(v)
        if not _NAME_PATTERN.match(v):
            raise ValueError("Name contains invalid characters")
        return v

    @field_validator("plc_type")
    @classmethod
    def _v_plc_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in PLC_TYPES:
            raise ValueError(f'Invalid PLC type. Must be one of: {", ".join(PLC_TYPES)}')
        return v

    @field_validator("ip_address")
    @classmethod
    def _v_ip(cls, v: str) -> str:
        v = v.strip()
        if not _IP_V4_PATTERN.match(v):
            raise ValueError(f"Invalid IP address: {v}")
        return v

    @field_validator("tcp_port")
    @classmethod
    def _v_tcp_port(cls, v: int) -> int:
        return _validate_range(v, TCP_PORT_MIN, TCP_PORT_MAX, "Port")

    @field_validator("rack")
    @classmethod
    def _v_rack(cls, v: int) -> int:
        return _validate_range(v, RACK_MIN, RACK_MAX, "Rack")

    @field_validator("slot")
    @classmethod
    def _v_slot(cls, v: int) -> int:
        return _validate_range(v, SLOT_MIN, SLOT_MAX, "Slot")

    @field_validator("slot_ab")
    @classmethod
    def _v_slot_ab(cls, v: int) -> int:
        return _validate_range(v, AB_SLOT_MIN, AB_SLOT_MAX, "AB Slot")
