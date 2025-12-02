"""
Pytest fixtures для тестов.
"""
import pytest
import tempfile
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.storage.models import Base, PLC, Tag, TrendData


@pytest.fixture
def temp_db():
    """Создание временной БД для тестов"""
    # Создаём временный файл
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Создаём движок и таблицы
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session, engine
    
    # Очистка
    session.close()
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def sample_plc(temp_db):
    """Создание тестового ПЛК"""
    session, _ = temp_db
    
    plc = PLC(
        name="TestPLC",
        ip_address="192.168.1.100",
        tcp_port=102,
        rack=0,
        slot=1,
        is_active=True
    )
    session.add(plc)
    session.commit()
    
    return plc


@pytest.fixture
def sample_tag(temp_db, sample_plc):
    """Создание тестового тега"""
    session, _ = temp_db
    
    tag = Tag(
        plc_id=sample_plc.id,
        name="Temperature",
        description="Test temperature",
        db_number=1,
        start_address=0,
        data_type="real",
        data_size=4,
        poll_interval_ms=1000,
        is_active=True
    )
    session.add(tag)
    session.commit()
    
    return tag


@pytest.fixture
def temp_config_file():
    """Создание временного config.yaml"""
    config_content = """
database:
  url: "sqlite:///test_trends.db"

collector:
  batch_size: 5
  flush_interval_sec: 1
  reconnect_delay_sec: 1

storage:
  retention_days: 7

plcs:
  - name: "TestPLC"
    ip: "127.0.0.1"
    port: 2000
    rack: 0
    slot: 1
    enabled: true
    tags:
      - name: "TestTag"
        description: "Test tag"
        db: 1
        address: 0
        type: "real"
        size: 4
        poll_ms: 100

logging:
  level: "DEBUG"
  file: "logs/test.log"
"""
    
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with os.fdopen(fd, 'w') as f:
        f.write(config_content)
    
    yield path
    
    os.unlink(path)
    # Удаляем тестовую БД если создалась
    if os.path.exists("test_trends.db"):
        os.unlink("test_trends.db")

