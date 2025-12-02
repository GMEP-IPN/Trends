"""
Сервис сбора данных с ПЛК.
Автоматически опрашивает теги и записывает значения в БД.
"""
import threading
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

from app.storage import get_session, PLC, Tag, TrendData
from app.collectors.S7Comm.siemens_s7 import PLC as S7Client
from app.config.settings import BATCH_INSERT_SIZE

logger = logging.getLogger('trends')


@dataclass
class TagValue:
    """Временное хранение значения тега перед записью в БД"""
    tag_id: int
    value: float
    timestamp: datetime
    quality: int = 192  # Good


class PLCConnection:
    """Обёртка для подключения к ПЛК с привязанными тегами"""
    
    def __init__(self, plc_config: PLC):
        self.plc_id = plc_config.id
        self.name = plc_config.name
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
        """Опрос одного тега"""
        try:
            value = self.client.read_db(
                db_number=tag.db_number,
                start=tag.start_address,
                size=tag.data_size,
                type_data=tag.data_type
            )
            
            self.last_poll[tag.id] = datetime.now()
            
            return TagValue(
                tag_id=tag.id,
                value=float(value),
                timestamp=datetime.now(),
                quality=192  # Good
            )
        except Exception as e:
            print(f"⚠️ Error polling tag {tag.name}: {e}")
            return TagValue(
                tag_id=tag.id,
                value=0.0,
                timestamp=datetime.now(),
                quality=0  # Bad
            )


class CollectorService:
    """
    Главный сервис сбора данных.
    
    Использование:
        service = CollectorService()
        service.start()
        # ... работает в фоне ...
        service.stop()
    """
    
    def __init__(self, flush_interval_sec: float = 5.0):
        self.connections: Dict[int, PLCConnection] = {}  # plc_id -> PLCConnection
        self.buffer: list[TagValue] = []  # Буфер для пакетной записи
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._flush_interval = flush_interval_sec
        self._last_flush = datetime.now()
    
    def load_configuration(self):
        """Загрузка конфигурации ПЛК и тегов из БД"""
        print("📋 Loading configuration from database...")
        
        with get_session() as session:
            # Загружаем активные ПЛК
            plcs = session.query(PLC).filter(PLC.is_active == True).all()
            
            for plc in plcs:
                print(f"  📡 Loading PLC: {plc.name} @ {plc.ip_address}:{plc.tcp_port}")
                conn = PLCConnection(plc)
                
                # Загружаем активные теги для этого ПЛК
                tags = session.query(Tag).filter(
                    Tag.plc_id == plc.id,
                    Tag.is_active == True
                ).all()
                
                for tag in tags:
                    # Делаем detached копию тега
                    conn.add_tag(Tag(
                        id=tag.id,
                        plc_id=tag.plc_id,
                        name=tag.name,
                        db_number=tag.db_number,
                        start_address=tag.start_address,
                        data_type=tag.data_type,
                        data_size=tag.data_size,
                        poll_interval_ms=tag.poll_interval_ms,
                        is_active=tag.is_active
                    ))
                
                self.connections[plc.id] = conn
                print(f"  ✅ PLC '{plc.name}' loaded with {len(tags)} tags")
        
        print(f"📋 Configuration loaded: {len(self.connections)} PLCs")
    
    def _flush_buffer(self):
        """Запись буфера в БД"""
        if not self.buffer:
            return
        
        with self._lock:
            to_write = self.buffer.copy()
            self.buffer.clear()
        
        with get_session() as session:
            for tv in to_write:
                trend = TrendData(
                    tag_id=tv.tag_id,
                    timestamp=tv.timestamp,
                    value=tv.value,
                    quality=tv.quality
                )
                session.add(trend)
        
        logger.info(f"Saved {len(to_write)} values to database")
    
    def _poll_cycle(self):
        """Один цикл опроса всех тегов"""
        for plc_id, conn in self.connections.items():
            for tag_id, tag in conn.tags.items():
                if conn.should_poll(tag_id):
                    result = conn.poll_tag(tag)
                    if result:
                        with self._lock:
                            self.buffer.append(result)
                        
                        # Выводим значение в консоль
                        quality_str = "✅" if result.quality == 192 else "❌"
                        print(f"  {quality_str} {tag.name}: {result.value}")
        
        # Сброс буфера при достижении лимита или по времени
        time_to_flush = (datetime.now() - self._last_flush).total_seconds() >= self._flush_interval
        if len(self.buffer) >= BATCH_INSERT_SIZE or (self.buffer and time_to_flush):
            self._flush_buffer()
            self._last_flush = datetime.now()
    
    def _run_loop(self):
        """Главный цикл сервиса"""
        print("🔄 Collector loop started")
        
        while self.running:
            try:
                self._poll_cycle()
                time.sleep(0.01)  # 10ms между проверками
            except Exception as e:
                print(f"❌ Error in collector loop: {e}")
                time.sleep(1)
        
        # Финальная запись буфера
        self._flush_buffer()
        print("🔄 Collector loop stopped")
    
    def start(self):
        """Запуск сервиса"""
        if self.running:
            print("⚠️ Collector already running")
            return
        
        print("🚀 Starting Collector Service...")
        
        # Загружаем конфигурацию
        self.load_configuration()
        
        if not self.connections:
            print("⚠️ No PLCs configured. Add PLCs and tags to database first.")
            return
        
        # Подключаемся к ПЛК
        for plc_id, conn in self.connections.items():
            print(f"🔌 Connecting to PLC '{conn.name}'...")
            conn.client.connect()
        
        # Запускаем цикл опроса в отдельном потоке
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        print("✅ Collector Service started")
    
    def stop(self):
        """Остановка сервиса"""
        if not self.running:
            return
        
        print("🛑 Stopping Collector Service...")
        self.running = False
        
        if self._thread:
            self._thread.join(timeout=5)
        
        # Отключаемся от ПЛК
        for plc_id, conn in self.connections.items():
            conn.client.disconnect()
        
        print("✅ Collector Service stopped")
    
    def get_status(self) -> dict:
        """Получение статуса сервиса"""
        return {
            "running": self.running,
            "plc_count": len(self.connections),
            "buffer_size": len(self.buffer),
            "connections": {
                conn.name: {
                    "connected": conn.client.connected,
                    "tag_count": len(conn.tags)
                }
                for conn in self.connections.values()
            }
        }


# Глобальный экземпляр сервиса
collector = CollectorService()

