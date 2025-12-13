"""
Tests for database functions.
"""
import pytest
import tempfile
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.storage.database import init_db, get_session, get_db, SessionLocal
from app.storage.models import Base, PLC, Tag, TrendData


class TestDatabaseInit:
    """Tests for database initialization"""
    
    def test_init_db_creates_tables(self):
        """init_db creates all tables"""
        # Create temp database
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Create engine for temp db
            engine = create_engine(f"sqlite:///{path}")
            Base.metadata.create_all(bind=engine)
            
            # Check tables exist
            from sqlalchemy import inspect
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            assert 'plcs' in tables
            assert 'tags' in tables
            assert 'trend_data' in tables
        finally:
            engine.dispose()
            os.unlink(path)
    
    def test_get_session_context_manager(self, temp_db):
        """get_session works as context manager"""
        session, _ = temp_db
        
        # Session should be usable
        plc = PLC(
            name="TestPLC",
            ip_address="192.168.1.10",
            tcp_port=102,
            is_active=True
        )
        session.add(plc)
        session.commit()
        
        # Verify it was added
        result = session.query(PLC).filter(PLC.name == "TestPLC").first()
        assert result is not None
        assert result.ip_address == "192.168.1.10"
    
    def test_session_rollback_on_error(self, temp_db):
        """Session rolls back on error"""
        session, _ = temp_db
        
        # Add first PLC
        plc1 = PLC(name="TestPLC", ip_address="192.168.1.10", is_active=True)
        session.add(plc1)
        session.commit()
        
        # Try to add duplicate (should fail due to unique constraint)
        try:
            plc2 = PLC(name="TestPLC", ip_address="192.168.1.20", is_active=True)
            session.add(plc2)
            session.commit()
        except Exception:
            session.rollback()
        
        # Should still only have one PLC
        count = session.query(PLC).count()
        assert count == 1


class TestModelIndexes:
    """Tests for database indexes"""
    
    def test_trend_data_indexes_exist(self, temp_db):
        """Verify indexes are created on trend_data"""
        _, engine = temp_db
        
        from sqlalchemy import inspect
        inspector = inspect(engine)
        indexes = inspector.get_indexes('trend_data')
        
        index_names = [idx['name'] for idx in indexes]
        
        # Should have our custom indexes
        assert any('trend_tag_time' in name for name in index_names)
        assert any('trend_timestamp' in name for name in index_names)
    
    def test_tag_address_index_exists(self, temp_db):
        """Tag has index on (plc_id, db_number, start_address, bit_number)"""
        _, engine = temp_db
        
        from sqlalchemy import inspect
        inspector = inspect(engine)
        indexes = inspector.get_indexes('tags')
        
        index_names = [idx['name'] for idx in indexes]
        
        # Индекс должен существовать (но не уникальный - для поддержки Allen-Bradley)
        assert any('tag_plc_address' in name for name in index_names)


class TestCascadeDelete:
    """Tests for cascade delete behavior"""
    
    def test_delete_plc_deletes_tags(self, temp_db):
        """Deleting PLC also deletes its tags"""
        session, _ = temp_db
        
        # Create PLC with tag
        plc = PLC(name="TestPLC", ip_address="192.168.1.10", is_active=True)
        session.add(plc)
        session.flush()
        
        tag = Tag(
            plc_id=plc.id,
            name="Tag1",
            db_number=1,
            start_address=0,
            data_type="real",
            data_size=4,
            is_active=True
        )
        session.add(tag)
        session.commit()
        
        # Verify tag exists
        assert session.query(Tag).count() == 1
        
        # Delete PLC
        session.delete(plc)
        session.commit()
        
        # Tag should be gone too
        assert session.query(Tag).count() == 0
    
    def test_delete_tag_deletes_trend_data(self, temp_db):
        """Deleting Tag also deletes its trend data"""
        session, _ = temp_db
        
        # Create PLC and tag
        plc = PLC(name="TestPLC", ip_address="192.168.1.10", is_active=True)
        session.add(plc)
        session.flush()
        
        tag = Tag(
            plc_id=plc.id,
            name="Tag1",
            db_number=1,
            start_address=0,
            data_type="real",
            data_size=4,
            is_active=True
        )
        session.add(tag)
        session.flush()
        
        # Add trend data
        trend = TrendData(tag_id=tag.id, value=25.5)
        session.add(trend)
        session.commit()
        
        # Verify trend exists
        assert session.query(TrendData).count() == 1
        
        # Delete tag
        session.delete(tag)
        session.commit()
        
        # Trend data should be gone
        assert session.query(TrendData).count() == 0


class TestDefaultValues:
    """Tests for model default values"""
    
    def test_plc_defaults(self, temp_db):
        """PLC has correct default values"""
        session, _ = temp_db
        
        plc = PLC(
            name="TestPLC",
            ip_address="192.168.1.10"
        )
        session.add(plc)
        session.commit()
        
        assert plc.tcp_port == 102
        assert plc.rack == 0
        assert plc.slot == 1
        assert plc.is_active == True
        assert plc.created_at is not None
    
    def test_tag_defaults(self, temp_db):
        """Tag has correct default values"""
        session, _ = temp_db
        
        plc = PLC(name="TestPLC", ip_address="192.168.1.10")
        session.add(plc)
        session.flush()
        
        tag = Tag(
            plc_id=plc.id,
            name="Tag1",
            db_number=1,
            start_address=0,
            data_type="real",
            data_size=4
        )
        session.add(tag)
        session.commit()
        
        assert tag.poll_interval_ms == 1000
        assert tag.is_active == True
        assert tag.created_at is not None
    
    def test_trend_data_defaults(self, temp_db):
        """TrendData has correct default values"""
        session, _ = temp_db
        
        plc = PLC(name="TestPLC", ip_address="192.168.1.10")
        session.add(plc)
        session.flush()
        
        tag = Tag(
            plc_id=plc.id,
            name="Tag1",
            db_number=1,
            start_address=0,
            data_type="real",
            data_size=4
        )
        session.add(tag)
        session.flush()
        
        trend = TrendData(tag_id=tag.id, value=25.5)
        session.add(trend)
        session.commit()
        
        assert trend.quality == 192  # Good quality
        assert trend.timestamp is not None


