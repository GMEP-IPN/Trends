"""
Тесты для моделей БД.
"""
import pytest
from datetime import datetime

from app.storage.models import PLC, Tag, TrendData


class TestPLCModel:
    """Тесты модели PLC"""
    
    def test_create_plc(self, temp_db):
        """Создание ПЛК"""
        session, _ = temp_db
        
        plc = PLC(
            name="TestPLC",
            ip_address="192.168.1.10",
            tcp_port=102,
            rack=0,
            slot=1
        )
        session.add(plc)
        session.commit()
        
        assert plc.id is not None
        assert plc.name == "TestPLC"
        assert plc.ip_address == "192.168.1.10"
        assert plc.is_active == True  # default
    
    def test_plc_repr(self, sample_plc):
        """Строковое представление ПЛК"""
        assert "TestPLC" in repr(sample_plc)
        assert "192.168.1.100" in repr(sample_plc)
    
    def test_plc_unique_name(self, temp_db, sample_plc):
        """Имя ПЛК должно быть уникальным"""
        session, _ = temp_db
        
        duplicate = PLC(
            name="TestPLC",  # Такое же имя
            ip_address="192.168.1.200",
            tcp_port=102,
            rack=0,
            slot=2
        )
        session.add(duplicate)
        
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestTagModel:
    """Тесты модели Tag"""
    
    def test_create_tag(self, temp_db, sample_plc):
        """Создание тега"""
        session, _ = temp_db
        
        tag = Tag(
            plc_id=sample_plc.id,
            name="Pressure",
            db_number=1,
            start_address=4,
            data_type="real",
            data_size=4,
            poll_interval_ms=500
        )
        session.add(tag)
        session.commit()
        
        assert tag.id is not None
        assert tag.plc_id == sample_plc.id
        assert tag.poll_interval_ms == 500
    
    def test_tag_plc_relationship(self, temp_db, sample_tag):
        """Связь тега с ПЛК"""
        assert sample_tag.plc is not None
        assert sample_tag.plc.name == "TestPLC"
    
    def test_tag_repr(self, sample_tag):
        """Строковое представление тега"""
        assert "Temperature" in repr(sample_tag)
        assert "DB1" in repr(sample_tag)
    
    def test_tag_unique_address(self, temp_db, sample_plc, sample_tag):
        """Адрес тега уникален в рамках ПЛК"""
        session, _ = temp_db
        
        duplicate = Tag(
            plc_id=sample_plc.id,
            name="DuplicateTag",
            db_number=1,      # Тот же DB
            start_address=0,  # Тот же адрес
            data_type="int",
            data_size=2
        )
        session.add(duplicate)
        
        with pytest.raises(Exception):
            session.commit()


class TestTrendDataModel:
    """Тесты модели TrendData"""
    
    def test_create_trend_data(self, temp_db, sample_tag):
        """Создание записи тренда"""
        session, _ = temp_db
        
        trend = TrendData(
            tag_id=sample_tag.id,
            timestamp=datetime.now(),
            value=25.5,
            quality=192
        )
        session.add(trend)
        session.commit()
        
        assert trend.id is not None
        assert trend.value == 25.5
        assert trend.quality == 192
    
    def test_trend_tag_relationship(self, temp_db, sample_tag):
        """Связь тренда с тегом"""
        session, _ = temp_db
        
        trend = TrendData(
            tag_id=sample_tag.id,
            value=30.0
        )
        session.add(trend)
        session.commit()
        
        assert trend.tag is not None
        assert trend.tag.name == "Temperature"
    
    def test_trend_default_values(self, temp_db, sample_tag):
        """Значения по умолчанию"""
        session, _ = temp_db
        
        trend = TrendData(
            tag_id=sample_tag.id,
            value=20.0
        )
        session.add(trend)
        session.commit()
        
        assert trend.quality == 192  # Good quality default
        assert trend.timestamp is not None
    
    def test_multiple_trends(self, temp_db, sample_tag):
        """Множественные записи трендов"""
        session, _ = temp_db
        
        for i in range(10):
            trend = TrendData(
                tag_id=sample_tag.id,
                value=20.0 + i * 0.5
            )
            session.add(trend)
        
        session.commit()
        
        count = session.query(TrendData).filter(
            TrendData.tag_id == sample_tag.id
        ).count()
        
        assert count == 10

