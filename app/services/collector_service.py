"""
Сервис сбора данных с ПЛК.
Автоматически опрашивает теги и записывает значения в БД.
Поддерживает Siemens S7 и Allen-Bradley контроллеры.
"""
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional, Union, Any
from dataclasses import dataclass

from app.storage import get_session, PLC, Tag, TrendData
from app.storage.database import get_monthly_session, IS_TESTING
from app.storage.models import PLC_TYPE_SIEMENS_S7, PLC_TYPE_ALLEN_BRADLEY
from app.collectors.S7Comm.siemens_s7 import PLC as S7Client, PLCConnectionError, PLCReadError
from app.config.settings import BATCH_INSERT_SIZE
from app.services.trend_service import cleanup_old_data
from app.services.collector_status import collector_status
from app.services.runtime_config import runtime_config

# Пытаемся импортировать Allen-Bradley клиент
try:
    from app.collectors.EtherNetIP.allen_bradley import ABClient, ABConnectionError, ABReadError
    AB_AVAILABLE = True
except ImportError:
    AB_AVAILABLE = False
    ABClient = None
    ABConnectionError = PLCConnectionError
    ABReadError = PLCReadError

logger = logging.getLogger('trends')


@dataclass
class TagValue:
    """Временное хранение значения тега перед записью в БД"""
    tag_id: int
    value: float
    timestamp: datetime
    quality: int = 192  # Good


class PLCConnection:
    """Обёртка для подключения к ПЛК с привязанными тегами. Поддерживает разные типы ПЛК."""
    
    def __init__(self, plc_config: PLC):
        self.plc_id = plc_config.id
        self.name = plc_config.name
        self.plc_type = getattr(plc_config, 'plc_type', PLC_TYPE_SIEMENS_S7)
        
        # Создаём клиент в зависимости от типа ПЛК
        if self.plc_type == PLC_TYPE_ALLEN_BRADLEY:
            if runtime_config.simulate_mode:
                # В режиме симуляции не нужен реальный клиент
                self.client = None
            elif not AB_AVAILABLE:
                raise RuntimeError("Allen-Bradley support not available. Install pycomm3: pip install pycomm3")
            else:
                self.client = ABClient(
                    plc_ip=plc_config.ip_address,
                    slot=getattr(plc_config, 'slot_ab', 0)
                )
        else:
            # По умолчанию Siemens S7
            self.client = S7Client(
                plc_ip=plc_config.ip_address,
                tcp_port=plc_config.tcp_port,
                rack=plc_config.rack,
                slot=plc_config.slot
            )
        
        self.tags: Dict[int, Tag] = {}  # tag_id -> Tag
        self.last_poll: Dict[int, datetime] = {}  # tag_id -> last poll time
    
    def add_tag(self, tag: Tag):
        self.tags[tag.id] = tag
        self.last_poll[tag.id] = datetime.min
    
    def should_poll(self, tag_id: int) -> bool:
        """Проверка, пора ли опрашивать тег"""
        tag = self.tags.get(tag_id)
        if not tag or not tag.is_active:
            return False
        
        elapsed_ms = (datetime.now() - self.last_poll[tag_id]).total_seconds() * 1000
        return elapsed_ms >= tag.poll_interval_ms
    
    def poll_tag(self, tag: Tag) -> Optional[TagValue]:
        """
        Опрос одного тега. Автоматически выбирает метод чтения в зависимости от типа ПЛК.
        
        Returns:
            TagValue с данными или None если не удалось прочитать
        """
        try:
            # Выбираем метод чтения в зависимости от типа ПЛК
            if self.plc_type == PLC_TYPE_ALLEN_BRADLEY:
                value = self._read_ab_tag(tag)
            else:
                value = self._read_s7_tag(tag)
            
            if value is None:
                return None
            
            # Validate value
            float_value = float(value)
            
            # Check for NaN or Infinity
            import math
            if math.isnan(float_value) or math.isinf(float_value):
                logger.warning(f"Invalid value (NaN/Inf) for tag {tag.name}, skipping")
                return None
            
            # Check for extreme values (likely garbage data)
            if abs(float_value) > 1e9:
                logger.warning(f"Extreme value {float_value} for tag {tag.name}, skipping")
                return None
            
            self.last_poll[tag.id] = datetime.now()
            
            return TagValue(
                tag_id=tag.id,
                value=float_value,
                timestamp=datetime.now(),
                quality=192  # Good (OPC standard)
            )
        except (PLCReadError, ABReadError) as e:
            logger.warning(f"Read error for tag {tag.name}: {e}")
            collector_status.set_plc_status(self.plc_id, False, str(e))
            return None
        except (PLCConnectionError, ABConnectionError) as e:
            logger.error(f"Connection error for tag {tag.name}: {e}")
            collector_status.set_plc_status(self.plc_id, False, str(e))
            return None
        except ValueError as e:
            logger.error(f"Invalid data type for tag {tag.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error polling tag {tag.name}: {e}")
            return None
    
    def _read_s7_tag(self, tag: Tag) -> Optional[Any]:
        """Чтение тега Siemens S7"""
        memory_area = getattr(tag, 'memory_area', None) or "DB"
        
        logger.debug(f"Reading tag {tag.name}: area={memory_area}, db={tag.db_number}, addr={tag.start_address}")
        
        return self.client.read_area(
            area=memory_area,
            db_number=tag.db_number or 0,
            start=tag.start_address,
            size=tag.data_size,
            type_data=tag.data_type,
            bit_number=getattr(tag, 'bit_number', 0)
        )
    
    def _read_ab_tag(self, tag: Tag) -> Optional[Any]:
        """Чтение тега Allen-Bradley"""
        # В режиме симуляции генерируем данные
        if runtime_config.simulate_mode:
            return self._simulate_ab_tag(tag)
        
        # Для AB используем имя тега
        ab_tag_name = getattr(tag, 'ab_tag_name', None)
        if not ab_tag_name:
            logger.error(f"No AB tag name configured for tag {tag.name}")
            return None
        return self.client.read_tag(ab_tag_name)
    
    def _simulate_ab_tag(self, tag: Tag) -> Any:
        """Генерация симулированных данных для AB тега"""
        import math
        import random
        
        # Получаем имя тега для определения паттерна
        tag_name = getattr(tag, 'ab_tag_name', None) or tag.name
        data_type = (tag.data_type or 'real').lower()
        
        # Текущее время для генерации волн
        t = time.time()
        
        # Генерируем значение в зависимости от имени тега
        if 'temp' in tag_name.lower():
            # Температура: 20-30°C с синусоидальной вариацией
            return 25.0 + 5.0 * math.sin(t / 30) + random.uniform(-0.5, 0.5)
        elif 'pressure' in tag_name.lower():
            # Давление: 750-770 мм рт.ст.
            return 760.0 + 10.0 * math.sin(t / 45 + 1) + random.uniform(-1, 1)
        elif 'flow' in tag_name.lower():
            # Расход: 50-100 л/мин
            return 75.0 + 25.0 * math.sin(t / 20) + random.uniform(-2, 2)
        elif 'level' in tag_name.lower():
            # Уровень: 0-100%
            return 50.0 + 40.0 * math.sin(t / 60 + 2) + random.uniform(-1, 1)
        elif 'speed' in tag_name.lower():
            # Скорость: 0-1500 об/мин
            return 750.0 + 500.0 * math.sin(t / 25 + 3) + random.uniform(-10, 10)
        elif 'count' in tag_name.lower() or 'counter' in tag_name.lower():
            # Счётчик: инкрементальное значение
            return int(t) % 10000
        elif 'running' in tag_name.lower() or 'status' in tag_name.lower():
            # Булевый статус
            return int(math.sin(t / 10) > 0)
        elif 'motor' in tag_name.lower() or 'pump' in tag_name.lower():
            # Булевый: двигатель/насос
            return int(math.sin(t / 15) > -0.3)
        elif 'alarm' in tag_name.lower():
            # Редкие алармы
            return int(random.random() < 0.05)
        
        # Для остальных тегов - генерируем по типу данных
        if data_type in ('bool', 'boolean'):
            return int(random.random() > 0.5)
        elif data_type in ('int', 'sint', 'usint'):
            return int(50 + 50 * math.sin(t / 10) + random.uniform(-5, 5))
        elif data_type in ('dint', 'udint', 'lint'):
            return int(1000 + 500 * math.sin(t / 20) + random.uniform(-20, 20))
        else:
            # REAL по умолчанию
            return 50.0 + 30.0 * math.sin(t / 15) + random.uniform(-2, 2)


class CollectorService:
    """
    Главный сервис сбора данных.
    
    Использование:
        service = CollectorService()
        service.start()
        # ... работает в фоне ...
        service.stop()
    """
    
    def __init__(
        self, 
        flush_interval_sec: float = 5.0, 
        retention_days: int = 30,
        cleanup_interval_hours: int = 6
    ):
        self.connections: Dict[int, PLCConnection] = {}  # plc_id -> PLCConnection
        self.buffer: list[TagValue] = []  # Буфер для пакетной записи
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._flush_interval = flush_interval_sec
        self._last_flush = datetime.now()
        
        # Настройки очистки старых данных (из config.yaml)
        self._retention_days = retention_days
        self._cleanup_interval_hours = cleanup_interval_hours
        self._last_cleanup = datetime.now()
    
    def load_configuration(self):
        """Загрузка конфигурации ПЛК и тегов из БД"""
        logger.info("Loading configuration from database...")
        
        with get_session() as session:
            # Загружаем активные ПЛК
            plcs = session.query(PLC).filter(PLC.is_active == True).all()
            
            for plc in plcs:
                plc_type = getattr(plc, 'plc_type', PLC_TYPE_SIEMENS_S7)
                type_label = "AB" if plc_type == PLC_TYPE_ALLEN_BRADLEY else "S7"
                logger.info(f"  Loading PLC [{type_label}]: {plc.name} @ {plc.ip_address}:{plc.tcp_port}")
                
                try:
                    conn = PLCConnection(plc)
                except RuntimeError as e:
                    logger.error(f"  Failed to create connection for '{plc.name}': {e}")
                    continue
                
                # Загружаем активные теги для этого ПЛК
                tags = session.query(Tag).filter(
                    Tag.plc_id == plc.id,
                    Tag.is_active == True
                ).all()
                
                for tag in tags:
                    # Делаем detached копию тега с учётом всех полей
                    tag_copy = Tag(
                        id=tag.id,
                        plc_id=tag.plc_id,
                        name=tag.name,
                        memory_area=getattr(tag, 'memory_area', None) or 'DB',  # S7 memory area
                        db_number=tag.db_number,
                        start_address=tag.start_address,
                        bit_number=tag.bit_number,
                        data_type=tag.data_type,
                        data_size=tag.data_size,
                        ab_tag_name=getattr(tag, 'ab_tag_name', None),  # Allen-Bradley tag name
                        poll_interval_ms=tag.poll_interval_ms,
                        is_active=tag.is_active
                    )
                    conn.add_tag(tag_copy)
                
                self.connections[plc.id] = conn
                logger.info(f"  PLC '{plc.name}' loaded with {len(tags)} tags")
        
        logger.info(f"Configuration loaded: {len(self.connections)} PLCs")
    
    def _flush_buffer(self):
        """Запись буфера в ежемесячные БД"""
        if not self.buffer:
            return
        
        with self._lock:
            to_write = self.buffer.copy()
            self.buffer.clear()
        
        # Группируем записи по месяцам
        grouped = {}
        for tv in to_write:
            key = (tv.timestamp.year, tv.timestamp.month)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(tv)
            
        for (year, month), items in grouped.items():
            dt = datetime(year, month, 1)
            session_ctx = get_session() if IS_TESTING else get_monthly_session(dt)
            with session_ctx as session:
                for tv in items:
                    trend = TrendData(
                        tag_id=tv.tag_id,
                        timestamp=tv.timestamp,
                        value=tv.value,
                        quality=tv.quality
                    )
                    session.add(trend)
        
        logger.info(f"Saved {len(to_write)} values to monthly databases")
    
    def _maybe_cleanup(self):
        """Периодическая очистка старых данных (отключено, используется помесячное разбиение БД)"""
        pass
    
    def _poll_cycle(self):
        """Один цикл опроса всех тегов"""
        for plc_id, conn in self.connections.items():
            for tag_id, tag in conn.tags.items():
                if conn.should_poll(tag_id):
                    result = conn.poll_tag(tag)
                    if result is not None:
                        with self._lock:
                            self.buffer.append(result)
                        
                        # Выводим значение в консоль (только успешные)
                        logger.debug(f"{tag.name}: {result.value}")
        
        # Сброс буфера при достижении лимита или по времени
        time_to_flush = (datetime.now() - self._last_flush).total_seconds() >= self._flush_interval
        if len(self.buffer) >= BATCH_INSERT_SIZE or (self.buffer and time_to_flush):
            self._flush_buffer()
            self._last_flush = datetime.now()
    
    def _run_loop(self):
        """Главный цикл сервиса"""
        logger.info("Collector loop started")
        
        while self.running:
            try:
                self._poll_cycle()
                time.sleep(0.01)  # 10ms между проверками
            except Exception as e:
                logger.error(f"Error in collector loop: {e}")
                time.sleep(1)
        
        # Финальная запись буфера
        self._flush_buffer()
        logger.info("Collector loop stopped")
    
    def start(self):
        """Запуск сервиса"""
        if self.running:
            logger.warning("Collector already running")
            return
        
        logger.info("Starting Collector Service...")
        
        # Загружаем конфигурацию
        self.load_configuration()
        
        if not self.connections:
            logger.warning("No PLCs configured. Add PLCs and tags to database first.")
            return
        
        # Подключаемся к ПЛК
        for plc_id, conn in self.connections.items():
            logger.info(f"Connecting to PLC '{conn.name}'...")
            try:
                # В режиме симуляции AB не требует подключения
                if conn.client is None:
                    logger.info(f"  PLC '{conn.name}' in simulation mode - no connection needed")
                    collector_status.set_plc_status(plc_id, True)
                    continue
                    
                conn.client.connect()
                if conn.client.connected:
                    collector_status.set_plc_status(plc_id, True)
                else:
                    collector_status.set_plc_status(plc_id, False, f"Connection failed")
            except Exception as e:
                collector_status.set_plc_status(plc_id, False, str(e))
        
        # Запускаем цикл опроса в отдельном потоке
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("Collector Service started")
    
    def stop(self):
        """Остановка сервиса"""
        if not self.running:
            return
        
        logger.info("Stopping Collector Service...")
        self.running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        # Отключаемся от ПЛК
        for plc_id, conn in self.connections.items():
            if conn.client is not None:
                conn.client.disconnect()
        
        logger.info("Collector Service stopped")
    
    def get_status(self) -> dict:
        """Получение статуса сервиса"""
        return {
            "running": self.running,
            "plc_count": len(self.connections),
            "buffer_size": len(self.buffer),
            "connections": {
                conn.name: {
                    "connected": conn.client.connected if conn.client else True,  # Simulation mode
                    "tag_count": len(conn.tags)
                }
                for conn in self.connections.values()
            }
        }

