"""
Тесты для сервиса трендов.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.storage.models import TrendData, Tag


class TestTrendService:
    """Тесты функций trend_service"""
    
    def test_get_trend_data(self, temp_db, sample_tag):
        """Получение данных тренда"""
        session, _ = temp_db
        
        # Создаём тестовые данные
        now = datetime.now()
        for i in range(5):
            trend = TrendData(
                tag_id=sample_tag.id,
                timestamp=now - timedelta(minutes=i),
                value=20.0 + i
            )
            session.add(trend)
        session.commit()
        
        # Мокаем get_session
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_trend_data
            
            data = get_trend_data(
                sample_tag.id,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(minutes=1)
            )
            
            assert len(data) == 5
            assert all(isinstance(d, tuple) for d in data)
    
    def test_get_latest_value(self, temp_db, sample_tag):
        """Получение последнего значения"""
        session, _ = temp_db
        
        # Создаём записи с разным временем
        old_time = datetime.now() - timedelta(hours=1)
        new_time = datetime.now()
        
        session.add(TrendData(tag_id=sample_tag.id, timestamp=old_time, value=10.0))
        session.add(TrendData(tag_id=sample_tag.id, timestamp=new_time, value=99.9))
        session.commit()
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_value
            
            result = get_latest_value(sample_tag.id)
            
            assert result is not None
            assert result[1] == 99.9  # Последнее значение
    
    def test_get_latest_value_empty(self, temp_db, sample_tag):
        """Получение последнего значения при пустой БД"""
        session, _ = temp_db
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_value
            
            result = get_latest_value(sample_tag.id)
            
            assert result is None
    
    def test_get_statistics(self, temp_db, sample_tag):
        """Получение статистики"""
        session, _ = temp_db
        
        # Создаём данные: 10, 20, 30, 40, 50
        now = datetime.now()
        for i in range(5):
            trend = TrendData(
                tag_id=sample_tag.id,
                timestamp=now - timedelta(minutes=i),
                value=10.0 + i * 10
            )
            session.add(trend)
        session.commit()
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_statistics
            
            stats = get_statistics(
                sample_tag.id,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(minutes=1)
            )
            
            assert stats['min'] == 10.0
            assert stats['max'] == 50.0
            assert stats['avg'] == 30.0  # (10+20+30+40+50)/5
            assert stats['count'] == 5
    
    def test_cleanup_old_data(self, temp_db, sample_tag):
        """Очистка старых данных"""
        session, _ = temp_db
        
        now = datetime.now()
        
        # Старые записи (40 дней назад)
        for i in range(3):
            session.add(TrendData(
                tag_id=sample_tag.id,
                timestamp=now - timedelta(days=40),
                value=i
            ))
        
        # Новые записи (1 день назад)
        for i in range(5):
            session.add(TrendData(
                tag_id=sample_tag.id,
                timestamp=now - timedelta(days=1),
                value=i + 100
            ))
        
        session.commit()
        
        # Всего 8 записей
        assert session.query(TrendData).count() == 8
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import cleanup_old_data
            
            deleted = cleanup_old_data(days=30)
            
            assert deleted == 3  # Удалены старые записи
        
        # Осталось 5 новых
        assert session.query(TrendData).count() == 5


class TestGetLatestValuesBatch:
    """Tests for get_latest_values_batch function"""
    
    def test_batch_empty_list(self, temp_db):
        """Empty tag_ids list returns empty dict"""
        session, _ = temp_db
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_values_batch
            
            result = get_latest_values_batch([])
            
            assert result == {}
    
    def test_batch_single_tag(self, temp_db, sample_tag):
        """Batch query for single tag"""
        session, _ = temp_db
        
        now = datetime.now()
        session.add(TrendData(tag_id=sample_tag.id, timestamp=now, value=42.0))
        session.commit()
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_values_batch
            
            result = get_latest_values_batch([sample_tag.id])
            
            assert sample_tag.id in result
            assert result[sample_tag.id][1] == 42.0
    
    def test_batch_multiple_values_returns_latest(self, temp_db, sample_tag):
        """Batch returns only latest value per tag"""
        session, _ = temp_db
        
        now = datetime.now()
        # Old value
        session.add(TrendData(
            tag_id=sample_tag.id, 
            timestamp=now - timedelta(hours=1), 
            value=10.0
        ))
        # Latest value
        session.add(TrendData(
            tag_id=sample_tag.id, 
            timestamp=now, 
            value=99.0
        ))
        session.commit()
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_values_batch
            
            result = get_latest_values_batch([sample_tag.id])
            
            assert result[sample_tag.id][1] == 99.0  # Latest, not 10.0
    
    def test_batch_missing_tags(self, temp_db, sample_tag):
        """Tags without data are not in result"""
        session, _ = temp_db
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            from app.services.trend_service import get_latest_values_batch
            
            # Tag exists but no trend data
            result = get_latest_values_batch([sample_tag.id, 999])
            
            assert sample_tag.id not in result
            assert 999 not in result


class TestGetAllTags:
    """Tests for get_all_tags function"""
    
    def test_get_all_tags(self, temp_db, sample_tag):
        """Get list of all tags"""
        session, _ = temp_db
        
        # Add value
        session.add(TrendData(
            tag_id=sample_tag.id,
            value=25.5
        ))
        session.commit()
        
        with patch('app.services.trend_service.get_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=session)
            mock_session.return_value.__exit__ = MagicMock(return_value=False)
            
            # Mock get_latest_value
            with patch('app.services.trend_service.get_latest_value') as mock_latest:
                mock_latest.return_value = (datetime.now(), 25.5)
                
                from app.services.trend_service import get_all_tags
                
                tags = get_all_tags()
                
                assert len(tags) == 1
                assert tags[0]['name'] == "Temperature"
                assert tags[0]['latest_value'] == 25.5

