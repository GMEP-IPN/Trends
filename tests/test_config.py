"""
Тесты для загрузчика конфигурации.
ПЛК и теги теперь хранятся в БД, поэтому тестируем только системные настройки.
"""
import pytest
import tempfile
import os

from app.config.config_loader import load_config, AppConfig


class TestConfigLoader:
    """Тесты загрузки конфигурации"""
    
    def test_load_config(self, temp_config_file):
        """Загрузка конфигурации из файла"""
        config = load_config(temp_config_file)
        
        assert isinstance(config, AppConfig)
        assert config.database_url == "sqlite:///test_trends.db"
        assert config.batch_size == 5
        assert config.flush_interval_sec == 1
    
    def test_config_not_found(self):
        """Ошибка при отсутствии файла"""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")
    
    def test_default_values(self):
        """Значения по умолчанию"""
        config_content = """
# Minimal config
database:
  url: "sqlite:///trends.db"
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            # Проверяем дефолты
            assert config.database_url == "sqlite:///trends.db"
            assert config.batch_size == 100  # default from config_loader
            assert config.flush_interval_sec == 5
            assert config.retention_days == 30
            assert config.log_level == "INFO"
            assert config.api_host == "127.0.0.1"
            assert config.api_port == 8000
        finally:
            os.unlink(path)
    
    def test_custom_api_settings(self):
        """Custom API settings"""
        config_content = """
database:
  url: "sqlite:///custom.db"
  
api:
  host: "0.0.0.0"
  port: 9000
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            assert config.api_host == "0.0.0.0"
            assert config.api_port == 9000
        finally:
            os.unlink(path)
    
    def test_collector_settings(self):
        """Collector settings"""
        config_content = """
database:
  url: "sqlite:///trends.db"

collector:
  batch_size: 50
  flush_interval_sec: 10
  reconnect_delay_sec: 30
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            assert config.batch_size == 50
            assert config.flush_interval_sec == 10
            assert config.reconnect_delay_sec == 30
        finally:
            os.unlink(path)
    
    def test_storage_settings(self):
        """Storage settings"""
        config_content = """
database:
  url: "sqlite:///trends.db"

storage:
  retention_days: 90
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            assert config.retention_days == 90
        finally:
            os.unlink(path)
    
    def test_logging_settings(self):
        """Logging settings"""
        config_content = """
database:
  url: "sqlite:///trends.db"

logging:
  level: "DEBUG"
  file: "logs/custom.log"
"""
        fd, path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        try:
            config = load_config(path)
            
            assert config.log_level == "DEBUG"
            assert config.log_file == "logs/custom.log"
        finally:
            os.unlink(path)


class TestAppConfig:
    """Тесты AppConfig dataclass"""
    
    def test_app_config_creation(self):
        """Создание AppConfig"""
        config = AppConfig(
            database_url="sqlite:///test.db",
            batch_size=10,
            flush_interval_sec=5.0,
            reconnect_delay_sec=5,
            retention_days=30,
            api_host="127.0.0.1",
            api_port=8000,
            log_level="INFO",
            log_file="logs/test.log"
        )
        
        assert config.database_url == "sqlite:///test.db"
        assert config.batch_size == 10
        assert config.api_port == 8000
