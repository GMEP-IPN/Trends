"""
Загрузчик конфигурации из YAML файла.
ПЛК и теги хранятся в БД и управляются через UI.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass 
class AppConfig:
    """Системная конфигурация приложения"""
    # База данных
    database_url: str
    
    # Коллектор
    batch_size: int
    flush_interval_sec: float
    reconnect_delay_sec: int
    
    # Хранение
    retention_days: int
    
    # API
    api_host: str
    api_port: int
    
    # Логирование
    log_level: str
    log_file: str


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Загрузка системных настроек из YAML файла.
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        AppConfig объект с настройками
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # Собираем конфиг только из системных настроек
    return AppConfig(
        # База данных
        database_url=data.get('database', {}).get('url', 'sqlite:///trends.db'),
        
        # Коллектор
        batch_size=data.get('collector', {}).get('batch_size', 100),
        flush_interval_sec=data.get('collector', {}).get('flush_interval_sec', 5),
        reconnect_delay_sec=data.get('collector', {}).get('reconnect_delay_sec', 5),
        
        # Хранение
        retention_days=data.get('storage', {}).get('retention_days', 30),
        
        # API
        api_host=data.get('api', {}).get('host', '127.0.0.1'),
        api_port=data.get('api', {}).get('port', 8000),
        
        # Логирование
        log_level=data.get('logging', {}).get('level', 'INFO'),
        log_file=data.get('logging', {}).get('file', 'logs/collector.log'),
    )


def setup_logging(config: AppConfig) -> logging.Logger:
    """
    Настройка логирования.
    
    Args:
        config: Конфигурация приложения
        
    Returns:
        Настроенный логгер
    """
    # Создаём директорию для логов
    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Настраиваем логгер
    logger = logging.getLogger('trends')
    logger.setLevel(getattr(logging, config.log_level.upper()))
    
    # Очищаем старые хендлеры
    logger.handlers.clear()
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Хендлер для файла
    file_handler = logging.FileHandler(config.log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Хендлер для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Глобальный конфиг и логгер
_config: Optional[AppConfig] = None
_logger: Optional[logging.Logger] = None


def get_config() -> AppConfig:
    """Получение глобального конфига"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_logger() -> logging.Logger:
    """Получение глобального логгера"""
    global _logger
    if _logger is None:
        _logger = setup_logging(get_config())
    return _logger
