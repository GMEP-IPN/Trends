"""
Тесты для загрузчика конфигурации.
"""
import pytest
import tempfile
import os

from app.config.config_loader import load_config, TagConfig, PLCConfig, AppConfig


class TestConfigLoader:
    """Тесты загрузки конфигурации"""
    
    def test_load_config(self, temp_config_file):
        """Загрузка конфигурации из файла"""
        config = load_config(temp_config_file)
        
        assert isinstance(config, AppConfig)
        assert config.database_url == "sqlite:///test_trends.db"
        assert config.batch_size == 5
        assert config.flush_interval_sec == 1
    
    def test_load_plcs(self, temp_config_file):
        """Загрузка ПЛК из конфигурации"""
        config = load_config(temp_config_file)
        
        assert len(config.plcs) == 1
        plc = config.plcs[0]
        
        assert isinstance(plc, PLCConfig)
        assert plc.name == "TestPLC"
        assert plc.ip == "127.0.0.1"
        assert plc.port == 2000
        assert plc.enabled == True
    
    def test_load_tags(self, temp_config_file):
        """Загрузка тегов из конфигурации"""
        config = load_config(temp_config_file)
        
        plc = config.plcs[0]
        assert len(plc.tags) == 1
        
        tag = plc.tags[0]
        assert isinstance(tag, TagConfig)
        assert tag.name == "TestTag"
        assert tag.db == 1
        assert tag.address == 0
        assert tag.type == "real"
        assert tag.size == 4
    
    def test_config_not_found(self):
        """Ошибка при отсутствии файла"""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")
    
    def test_default_values(self):
        """Значения по умолчанию"""
        config_content = """
plcs: []
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            # Проверяем дефолты
            assert config.database_url == "sqlite:///trends.db"
            assert config.batch_size == 10
            assert config.flush_interval_sec == 5
            assert config.retention_days == 30
            assert config.log_level == "INFO"
        finally:
            os.unlink(path)
    
    def test_multiple_plcs(self):
        """Множественные ПЛК"""
        config_content = """
plcs:
  - name: "PLC1"
    ip: "192.168.1.10"
    enabled: true
    tags: []
  - name: "PLC2"
    ip: "192.168.1.20"
    enabled: false
    tags: []
  - name: "PLC3"
    ip: "192.168.1.30"
    enabled: true
    tags: []
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            assert len(config.plcs) == 3
            assert config.plcs[0].enabled == True
            assert config.plcs[1].enabled == False
            assert config.plcs[2].enabled == True
        finally:
            os.unlink(path)


class TestTagConfig:
    """Тесты TagConfig dataclass"""
    
    def test_tag_config_creation(self):
        """Создание TagConfig"""
        tag = TagConfig(
            name="Test",
            description="Test tag",
            db=1,
            address=0,
            type="real",
            size=4,
            poll_ms=1000
        )
        
        assert tag.name == "Test"
        assert tag.poll_ms == 1000


class TestPLCConfig:
    """Тесты PLCConfig dataclass"""
    
    def test_plc_config_creation(self):
        """Создание PLCConfig"""
        plc = PLCConfig(
            name="TestPLC",
            ip="192.168.1.10",
            port=102,
            rack=0,
            slot=1,
            enabled=True,
            tags=[]
        )
        
        assert plc.name == "TestPLC"
        assert plc.port == 102
        assert len(plc.tags) == 0

