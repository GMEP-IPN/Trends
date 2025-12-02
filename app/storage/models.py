from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    ForeignKey, Boolean, Index
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class PLC(Base):
    """Конфигурация ПЛК"""
    __tablename__ = "plcs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    ip_address = Column(String(45), nullable=False)
    tcp_port = Column(Integer, default=102)
    rack = Column(Integer, default=0)
    slot = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с тегами
    tags = relationship("Tag", back_populates="plc", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PLC {self.name} ({self.ip_address})>"


class Tag(Base):
    """Тег для сбора данных"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    plc_id = Column(Integer, ForeignKey("plcs.id"), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    
    # Адресация S7
    db_number = Column(Integer, nullable=False)
    start_address = Column(Integer, nullable=False)  # Байтовое смещение
    data_type = Column(String(20), nullable=False)   # int, dint, real, bool, etc.
    data_size = Column(Integer, nullable=False)      # Размер в байтах
    
    # Настройки опроса
    poll_interval_ms = Column(Integer, default=1000)  # Интервал опроса в мс
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    plc = relationship("PLC", back_populates="tags")
    trend_data = relationship("TrendData", back_populates="tag", cascade="all, delete-orphan")

    # Уникальность: один тег на адрес в рамках ПЛК
    __table_args__ = (
        Index("ix_tag_plc_address", "plc_id", "db_number", "start_address", unique=True),
    )

    def __repr__(self):
        return f"<Tag {self.name} (DB{self.db_number}.DBW{self.start_address})>"


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

    # Индексы для быстрого поиска по времени
    __table_args__ = (
        Index("ix_trend_tag_time", "tag_id", "timestamp"),
        Index("ix_trend_timestamp", "timestamp"),
    )

    def __repr__(self):
        return f"<TrendData tag={self.tag_id} value={self.value} @ {self.timestamp}>"



