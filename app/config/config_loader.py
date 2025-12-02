"""
Загрузчик конфигурации из YAML файла.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class TagConfig:
    """Конфигурация тега"""
    name: str
    description: str
    db: int
    address: int
    type: str
    size: int
    poll_ms: int


@dataclass
class PLCConfig:
    """Конфигурация ПЛК"""
    name: str
    ip: str
    port: int
    rack: int
    slot: int
    enabled: bool
    tags: List[TagConfig]


@dataclass 
class AppConfig:
    """Главная конфигурация приложения"""
    database_url: str
    batch_size: int
    flush_interval_sec: float
    reconnect_delay_sec: int
    retention_days: int
    log_level: str
    log_file: str
    plcs: List[PLCConfig]


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Загрузка конфигурации из YAML файла.
    
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
    
    # Парсим ПЛК и теги
    plcs = []
    for plc_data in data.get('plcs', []):
        tags = []
        for tag_data in plc_data.get('tags', []):
            tags.append(TagConfig(
                name=tag_data['name'],
                description=tag_data.get('description', ''),
                db=tag_data['db'],
                address=tag_data['address'],
                type=tag_data['type'],
                size=tag_data['size'],
                poll_ms=tag_data.get('poll_ms', 1000)
            ))
        
        plcs.append(PLCConfig(
            name=plc_data['name'],
            ip=plc_data['ip'],
            port=plc_data.get('port', 102),
            rack=plc_data.get('rack', 0),
            slot=plc_data.get('slot', 1),
            enabled=plc_data.get('enabled', True),
            tags=tags
        ))
    
    # Собираем конфиг
    return AppConfig(
        database_url=data.get('database', {}).get('url', 'sqlite:///trends.db'),
        batch_size=data.get('collector', {}).get('batch_size', 10),
        flush_interval_sec=data.get('collector', {}).get('flush_interval_sec', 5),
        reconnect_delay_sec=data.get('collector', {}).get('reconnect_delay_sec', 5),
        retention_days=data.get('storage', {}).get('retention_days', 30),
        log_level=data.get('logging', {}).get('level', 'INFO'),
        log_file=data.get('logging', {}).get('file', 'logs/collector.log'),
        plcs=plcs
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


