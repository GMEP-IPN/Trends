from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    ForeignKey, Boolean, Index
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

# Типы ПЛК
PLC_TYPE_SIEMENS_S7 = "siemens_s7"
PLC_TYPE_ALLEN_BRADLEY = "allen_bradley"

PLC_TYPES = [PLC_TYPE_SIEMENS_S7, PLC_TYPE_ALLEN_BRADLEY]

# Области памяти Siemens S7
S7_AREA_DB = "DB"   # Data Blocks
S7_AREA_I = "I"     # Inputs (Входы)
S7_AREA_Q = "Q"     # Outputs (Выходы)
S7_AREA_M = "M"     # Markers (Маркеры)
S7_AREA_T = "T"     # Timers (Таймеры)
S7_AREA_C = "C"     # Counters (Счётчики)

S7_MEMORY_AREAS = [S7_AREA_DB, S7_AREA_I, S7_AREA_Q, S7_AREA_M, S7_AREA_T, S7_AREA_C]


class PLC(Base):
    """Конфигурация ПЛК"""
    __tablename__ = "plcs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    plc_type = Column(String(50), default=PLC_TYPE_SIEMENS_S7, nullable=False)  # siemens_s7 или allen_bradley
    ip_address = Column(String(45), nullable=False)
    tcp_port = Column(Integer, default=102)
    
    # Siemens S7 specific
    rack = Column(Integer, default=0)
    slot = Column(Integer, default=1)
    
    # Allen-Bradley specific
    slot_ab = Column(Integer, default=0)  # Slot для ControlLogix (обычно 0)
    
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с тегами
    tags = relationship("Tag", back_populates="plc", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PLC {self.name} ({self.plc_type}: {self.ip_address})>"


class Tag(Base):
    """Тег для сбора данных"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    plc_id = Column(Integer, ForeignKey("plcs.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    
    # Адресация S7 (опционально - только для Siemens)
    memory_area = Column(String(10), default="DB")    # DB, I, Q, M (область памяти S7)
    db_number = Column(Integer, nullable=True)        # NULL для Allen-Bradley или I/Q/M
    start_address = Column(Integer, nullable=True)    # NULL для Allen-Bradley
    bit_number = Column(Integer, default=0)           # Номер бита (0-7, только для BOOL в S7)
    data_type = Column(String(20), nullable=False)    # int, dint, real, bool, etc.
    data_size = Column(Integer, nullable=True)        # Размер в байтах (NULL для AB)
    
    # Адресация Allen-Bradley (опционально - только для AB)
    ab_tag_name = Column(String(255), nullable=True)  # Имя тега в ПЛК (например "Program:MainProgram.MyTag")
    
    # Настройки опроса
    poll_interval_ms = Column(Integer, default=1000)  # Интервал опроса в мс
    is_active = Column(Boolean, default=True)
    is_archived = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    plc = relationship("PLC", back_populates="tags")
    trend_data = relationship("TrendData", back_populates="tag", cascade="all, delete-orphan")

    # Индекс для поиска (без unique, т.к. AB теги не имеют db_number/start_address)
    __table_args__ = (
        Index("ix_tag_plc_area_address", "plc_id", "memory_area", "db_number", "start_address", "bit_number"),
        Index("ix_tag_plc_ab_tag", "plc_id", "ab_tag_name"),
    )

    def __repr__(self):
        if self.ab_tag_name:
            return f"<Tag {self.name} (AB: {self.ab_tag_name})>"
        if self.memory_area == "DB":
            return f"<Tag {self.name} (DB{self.db_number}.{self.start_address})>"
        return f"<Tag {self.name} ({self.memory_area}{self.start_address})>"


class TrendData(Base):
    """Записи трендов (time-series данные)"""
    __tablename__ = "trend_data"

    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    value = Column(Float, nullable=False)  # Все значения храним как float
    quality = Column(Integer, default=192)  # 192 = Good (OPC стандарт)

    # Связь
    tag = relationship("Tag", back_populates="trend_data")

    # Индексы для быстрого поиска
    __table_args__ = (
        # Основной индекс для запросов трендов по тегу и времени
        Index("ix_trend_tag_time", "tag_id", "timestamp"),
        # Индекс для запросов только по времени (cleanup)
        Index("ix_trend_timestamp", "timestamp"),
        # Индекс для быстрого получения последнего значения (DESC)
        Index("ix_trend_tag_time_desc", "tag_id", timestamp.desc()),
    )

    def __repr__(self):
        return f"<TrendData tag={self.tag_id} value={self.value} @ {self.timestamp}>"



