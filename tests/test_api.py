"""
Тесты для REST API.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.api.server import app
from app.services.collector_manager import collector_status


@pytest.fixture
def client():
    """Тестовый клиент FastAPI"""
    return TestClient(app)


@pytest.fixture
def reset_collector_status():
    """Сброс статуса коллектора перед тестом"""
    collector_status.running = False
    collector_status.connected = False
    collector_status.last_error = None
    collector_status.plc_name = None
    collector_status._restart_requested = False
    yield
    # Сброс после теста
    collector_status.running = False
    collector_status.connected = False
    collector_status._restart_requested = False


class TestStatusEndpoint:
    """Тесты endpoint /api/status"""
    
    def test_status_stopped(self, client, reset_collector_status):
        """Статус когда коллектор остановлен"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.count.return_value = 1
            session.query.return_value.count.return_value = 100
            session.query.return_value.order_by.return_value.first.return_value = None
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.get("/api/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["connection_status"] == "stopped"
            assert data["collector_running"] == False
    
    def test_status_connected(self, client, reset_collector_status):
        """Статус когда подключено"""
        collector_status.running = True
        collector_status.connected = True
        
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.count.return_value = 1
            session.query.return_value.count.return_value = 100
            session.query.return_value.order_by.return_value.first.return_value = None
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.get("/api/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["connection_status"] == "connected"
            assert data["collector_running"] == True
    
    def test_status_disconnected(self, client, reset_collector_status):
        """Статус когда отключено"""
        collector_status.running = True
        collector_status.connected = False
        
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.count.return_value = 1
            session.query.return_value.count.return_value = 100
            session.query.return_value.order_by.return_value.first.return_value = None
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.get("/api/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["connection_status"] == "disconnected"


class TestTagsEndpoint:
    """Тесты endpoint /api/tags"""
    
    def test_list_tags_empty(self, client):
        """Список тегов пуст"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.all.return_value = []
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            with patch('app.api.server.get_latest_values_batch') as mock_batch:
                mock_batch.return_value = {}
                
                response = client.get("/api/tags")
                
                assert response.status_code == 200
                assert response.json() == []
    
    def test_create_tag_success(self, client, reset_collector_status):
        """Успешное создание тега"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            
            # Мокаем PLC
            mock_plc = MagicMock()
            mock_plc.id = 1
            session.query.return_value.filter.return_value.first.side_effect = [
                mock_plc,  # Первый вызов - поиск PLC
                None       # Второй вызов - проверка существующего тега
            ]
            
            # Мокаем создание тега
            def flush_side_effect():
                pass
            session.flush = flush_side_effect
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            # Мокаем добавленный тег
            def add_side_effect(tag):
                tag.id = 10
            session.add = add_side_effect
            
            response = client.post("/api/tags", json={
                "name": "TestTag",
                "description": "Test description",
                "db_number": 1,
                "start_address": 100,
                "data_type": "real",
                "data_size": 4,
                "poll_interval_ms": 1000
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "TestTag"
            assert "message" in data
    
    def test_create_tag_no_plc(self, client):
        """Создание тега без активного ПЛК"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.post("/api/tags", json={
                "name": "TestTag",
                "db_number": 1,
                "start_address": 0,
                "data_type": "int",
                "data_size": 2
            })
            
            assert response.status_code == 404
            assert "No active PLC" in response.json()["detail"]
    
    def test_create_tag_duplicate_address(self, client):
        """Создание тега с существующим адресом"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            
            mock_plc = MagicMock()
            mock_plc.id = 1
            
            mock_existing_tag = MagicMock()
            mock_existing_tag.is_active = True  # Активный тег
            
            session.query.return_value.filter.return_value.first.side_effect = [
                mock_plc,          # PLC найден
                mock_existing_tag  # Тег уже существует
            ]
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.post("/api/tags", json={
                "name": "DuplicateTag",
                "db_number": 1,
                "start_address": 0,
                "data_type": "real",
                "data_size": 4
            })
            
            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
    
    def test_delete_tag_success(self, client, reset_collector_status):
        """Успешное удаление тега"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            
            mock_tag = MagicMock()
            mock_tag.id = 1
            mock_tag.name = "TestTag"
            mock_tag.is_active = True
            
            session.query.return_value.filter.return_value.first.return_value = mock_tag
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.delete("/api/tags/1")
            
            assert response.status_code == 200
            assert mock_tag.is_active == False
            assert "deleted" in response.json()["message"]
    
    def test_delete_tag_not_found(self, client):
        """Удаление несуществующего тега"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.delete("/api/tags/999")
            
            assert response.status_code == 404


class TestPLCsEndpoint:
    """Тесты endpoint /api/plcs"""
    
    def test_list_plcs(self, client):
        """Список ПЛК"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            
            mock_plc = MagicMock()
            mock_plc.id = 1
            mock_plc.name = "TestPLC"
            mock_plc.ip_address = "192.168.1.10"
            mock_plc.tcp_port = 102
            mock_plc.rack = 0
            mock_plc.slot = 1
            mock_plc.is_active = True
            
            session.query.return_value.filter.return_value.all.return_value = [mock_plc]
            session.query.return_value.filter.return_value.count.return_value = 2
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.get("/api/plcs")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "TestPLC"
            assert data[0]["rack"] == 0
            assert data[0]["slot"] == 1
    
    def test_create_plc_success(self, client, reset_collector_status):
        """Успешное создание ПЛК"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            
            def add_side_effect(plc):
                plc.id = 1
            session.add = add_side_effect
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.post("/api/plcs", json={
                "name": "NewPLC",
                "ip_address": "192.168.1.100",
                "tcp_port": 102,
                "rack": 0,
                "slot": 1
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "NewPLC"
            assert collector_status.restart_requested == True
    
    def test_create_plc_duplicate(self, client):
        """Создание ПЛК с существующим именем"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            mock_existing = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = mock_existing
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.post("/api/plcs", json={
                "name": "ExistingPLC",
                "ip_address": "192.168.1.100",
                "tcp_port": 102,
                "rack": 0,
                "slot": 1
            })
            
            assert response.status_code == 400
            assert "already exists" in response.json()["detail"]
    
    def test_delete_plc_success(self, client, reset_collector_status):
        """Успешное удаление ПЛК"""
        with patch('app.api.server.get_session') as mock_session:
            session = MagicMock()
            
            mock_plc = MagicMock()
            mock_plc.id = 1
            mock_plc.name = "TestPLC"
            mock_plc.is_active = True
            
            session.query.return_value.filter.return_value.first.return_value = mock_plc
            session.query.return_value.filter.return_value.update = MagicMock()
            
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.delete("/api/plcs/1")
            
            assert response.status_code == 200
            assert mock_plc.is_active == False
            assert collector_status.restart_requested == True


class TestTrendEndpoint:
    """Тесты endpoint /api/tags/{id}/trend"""
    
    def test_get_trend_data(self, client):
        """Получение данных тренда"""
        with patch('app.api.server.get_trend_data') as mock_get_trend:
            from datetime import datetime
            mock_get_trend.return_value = [
                (datetime(2025, 1, 1, 12, 0), 25.5),
                (datetime(2025, 1, 1, 12, 1), 26.0),
            ]
            
            response = client.get("/api/tags/1/trend?minutes=60")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["value"] == 25.5


class TestStatisticsEndpoint:
    """Тесты endpoint /api/tags/{id}/statistics"""
    
    def test_get_statistics(self, client):
        """Получение статистики"""
        with patch('app.api.server.get_statistics') as mock_stats:
            mock_stats.return_value = {
                "min": 20.0,
                "max": 30.0,
                "avg": 25.0,
                "count": 100,
                "start_time": "2025-01-01T00:00:00",
                "end_time": "2025-01-01T01:00:00"
            }
            
            response = client.get("/api/tags/1/statistics?minutes=60")
            
            assert response.status_code == 200
            data = response.json()
            assert data["min"] == 20.0
            assert data["max"] == 30.0
            assert data["avg"] == 25.0


class TestLatestEndpoint:
    """Тесты endpoint /api/tags/{id}/latest"""
    
    def test_get_latest_value(self, client):
        """Получение последнего значения"""
        with patch('app.api.server.get_latest_value') as mock_latest:
            from datetime import datetime
            mock_latest.return_value = (datetime(2025, 1, 1, 12, 0), 25.5)
            
            response = client.get("/api/tags/1/latest")
            
            assert response.status_code == 200
            data = response.json()
            assert data["value"] == 25.5
    
    def test_get_latest_value_not_found(self, client):
        """Последнее значение не найдено"""
        with patch('app.api.server.get_latest_value') as mock_latest:
            mock_latest.return_value = None
            
            response = client.get("/api/tags/1/latest")
            
            assert response.status_code == 404


class TestCollectorRestartEndpoint:
    """Тесты endpoint /api/collector/restart"""
    
    def test_restart_collector(self, client, reset_collector_status):
        """Запрос на перезапуск коллектора"""
        response = client.post("/api/collector/restart")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert collector_status.restart_requested == True
