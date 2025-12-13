"""
Тесты для сервиса сбора данных.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.collector_service import (
    TagValue, 
    PLCConnection, 
    CollectorService
)
from app.storage.models import PLC, Tag


class TestTagValue:
    """Тесты dataclass TagValue"""
    
    def test_create_tag_value(self):
        """Создание TagValue"""
        tv = TagValue(
            tag_id=1,
            value=25.5,
            timestamp=datetime.now(),
            quality=192
        )
        
        assert tv.tag_id == 1
        assert tv.value == 25.5
        assert tv.quality == 192
    
    def test_default_quality(self):
        """Качество по умолчанию"""
        tv = TagValue(
            tag_id=1,
            value=10.0,
            timestamp=datetime.now()
        )
        
        assert tv.quality == 192  # Good


class TestPLCConnection:
    """Тесты класса PLCConnection"""
    
    def test_create_connection(self):
        """Создание подключения"""
        plc_config = MagicMock()
        plc_config.id = 1
        plc_config.name = "TestPLC"
        plc_config.ip_address = "127.0.0.1"
        plc_config.tcp_port = 2000
        plc_config.rack = 0
        plc_config.slot = 1
        
        with patch('app.services.collector_service.S7Client'):
            conn = PLCConnection(plc_config)
            
            assert conn.plc_id == 1
            assert conn.name == "TestPLC"
            assert conn.tags == {}
    
    def test_add_tag(self):
        """Добавление тега"""
        plc_config = MagicMock()
        plc_config.id = 1
        plc_config.name = "TestPLC"
        plc_config.ip_address = "127.0.0.1"
        plc_config.tcp_port = 2000
        plc_config.rack = 0
        plc_config.slot = 1
        
        tag = MagicMock()
        tag.id = 10
        tag.is_active = True
        tag.poll_interval_ms = 1000
        
        with patch('app.services.collector_service.S7Client'):
            conn = PLCConnection(plc_config)
            conn.add_tag(tag)
            
            assert 10 in conn.tags
            assert conn.tags[10] == tag
    
    def test_should_poll(self):
        """Проверка необходимости опроса"""
        plc_config = MagicMock()
        plc_config.id = 1
        plc_config.name = "TestPLC"
        plc_config.ip_address = "127.0.0.1"
        plc_config.tcp_port = 2000
        plc_config.rack = 0
        plc_config.slot = 1
        
        tag = MagicMock()
        tag.id = 10
        tag.is_active = True
        tag.poll_interval_ms = 1000
        
        with patch('app.services.collector_service.S7Client'):
            conn = PLCConnection(plc_config)
            conn.add_tag(tag)
            
            # Первый опрос - всегда True
            assert conn.should_poll(10) == True


class TestCollectorService:
    """Тесты CollectorService"""
    
    def test_create_service(self):
        """Создание сервиса"""
        service = CollectorService(flush_interval_sec=5.0)
        
        assert service.running == False
        assert service._flush_interval == 5.0
        assert len(service.buffer) == 0
    
    def test_service_not_running_initially(self):
        """Сервис не запущен изначально"""
        service = CollectorService()
        
        assert service.running == False
        assert service._thread is None
    
    def test_get_status(self):
        """Получение статуса"""
        service = CollectorService()
        
        status = service.get_status()
        
        assert 'running' in status
        assert 'plc_count' in status
        assert 'buffer_size' in status
        assert status['running'] == False
    
    def test_buffer_operations(self):
        """Операции с буфером"""
        service = CollectorService()
        
        # Добавляем в буфер
        tv = TagValue(
            tag_id=1,
            value=25.0,
            timestamp=datetime.now()
        )
        
        service.buffer.append(tv)
        
        assert len(service.buffer) == 1
        assert service.get_status()['buffer_size'] == 1
    
    @patch('app.services.collector_service.get_session')
    def test_flush_empty_buffer(self, mock_session):
        """Сброс пустого буфера"""
        service = CollectorService()
        
        # Не должно вызывать ошибку
        service._flush_buffer()
        
        # get_session не должен вызываться
        mock_session.assert_not_called()
    
    @patch('app.services.collector_service.get_session')
    def test_flush_buffer_with_data(self, mock_session):
        """Сброс буфера с данными"""
        session = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=session)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        
        service = CollectorService()
        
        # Добавляем данные
        for i in range(3):
            service.buffer.append(TagValue(
                tag_id=1,
                value=i * 10.0,
                timestamp=datetime.now()
            ))
        
        service._flush_buffer()
        
        # Буфер должен очиститься
        assert len(service.buffer) == 0
        
        # session.add должен быть вызван 3 раза
        assert session.add.call_count == 3


class TestCollectorIntegration:
    """Интеграционные тесты коллектора"""
    
    def test_start_without_config(self):
        """Запуск без конфигурации"""
        service = CollectorService()
        
        with patch('app.services.collector_service.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.all.return_value = []
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            service.start()
            
            # Не должен запуститься без ПЛК
            assert service.running == False
    
    def test_stop_not_running(self):
        """Остановка незапущенного сервиса"""
        service = CollectorService()
        
        # Не должно вызывать ошибку
        service.stop()
        
        assert service.running == False




