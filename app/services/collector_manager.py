"""
Менеджер коллектора - единая точка управления.
Устраняет дублирование кода между run.py и trends_app.py
"""
import threading
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from app.services.collector_service import CollectorService

logger = logging.getLogger('trends')


@dataclass
class CollectorStatus:
    """
    Потокобезопасный статус коллектора.
    Использует блокировку для безопасного доступа из разных потоков.
    """
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _running: bool = False
    _connected: bool = False
    _last_error: Optional[str] = None
    _plc_name: Optional[str] = None
    _restart_requested: bool = False
    
    @property
    def running(self) -> bool:
        with self._lock:
            return self._running
    
    @running.setter
    def running(self, value: bool):
        with self._lock:
            self._running = value
    
    @property
    def connected(self) -> bool:
        with self._lock:
            return self._connected
    
    @connected.setter
    def connected(self, value: bool):
        with self._lock:
            self._connected = value
    
    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error
    
    @last_error.setter
    def last_error(self, value: Optional[str]):
        with self._lock:
            self._last_error = value
    
    @property
    def plc_name(self) -> Optional[str]:
        with self._lock:
            return self._plc_name
    
    @plc_name.setter
    def plc_name(self, value: Optional[str]):
        with self._lock:
            self._plc_name = value
    
    @property
    def restart_requested(self) -> bool:
        with self._lock:
            return self._restart_requested
    
    @restart_requested.setter
    def restart_requested(self, value: bool):
        with self._lock:
            self._restart_requested = value
    
    def request_restart(self):
        """Запросить перезапуск коллектора"""
        with self._lock:
            self._restart_requested = True
    
    def clear_restart_request(self) -> bool:
        """Очистить запрос на перезапуск, вернуть True если был запрошен"""
        with self._lock:
            was_requested = self._restart_requested
            self._restart_requested = False
            return was_requested
    
    def to_dict(self) -> Dict[str, Any]:
        """Получить все значения как словарь (потокобезопасно)"""
        with self._lock:
            return {
                "running": self._running,
                "connected": self._connected,
                "last_error": self._last_error,
                "plc_name": self._plc_name,
                "restart_requested": self._restart_requested
            }


# Глобальный потокобезопасный статус
collector_status = CollectorStatus()


class CollectorManager:
    """
    Менеджер коллектора - единая точка управления.
    Инкапсулирует логику запуска, остановки и перезапуска.
    """
    
    def __init__(
        self, 
        flush_interval_sec: float = 5.0,
        retention_days: int = 30,
        cleanup_interval_hours: int = 6
    ):
        self.flush_interval_sec = flush_interval_sec
        self.retention_days = retention_days
        self.cleanup_interval_hours = cleanup_interval_hours
        self.collector: Optional[CollectorService] = None
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """
        Запустить коллектор.
        
        Returns:
            True если запущен успешно
        """
        with self._lock:
            if self.collector and self.collector.running:
                logger.warning("Collector already running")
                return True
            
            self.collector = CollectorService(
                flush_interval_sec=self.flush_interval_sec,
                retention_days=self.retention_days,
                cleanup_interval_hours=self.cleanup_interval_hours
            )
            self.collector.start()
            
            # Обновляем статус
            collector_status.running = self.collector.running
            
            if self.collector.connections:
                for conn in self.collector.connections.values():
                    collector_status.connected = conn.client.connected
                    collector_status.plc_name = conn.name
                    break
            
            return self.collector.running
    
    def stop(self):
        """Остановить коллектор"""
        with self._lock:
            if self.collector:
                self.collector.stop()
                self.collector = None
            
            collector_status.running = False
            collector_status.connected = False
    
    def restart(self) -> bool:
        """
        Перезапустить коллектор с новой конфигурацией.
        
        Returns:
            True если перезапущен успешно
        """
        logger.info("🔄 Restarting collector...")
        
        with self._lock:
            if not self.collector:
                self.collector = CollectorService(
                    flush_interval_sec=self.flush_interval_sec,
                    retention_days=self.retention_days,
                    cleanup_interval_hours=self.cleanup_interval_hours
                )
            
            # Останавливаем текущий цикл
            self.collector.stop()
            self.collector.connections.clear()
            self.collector.buffer.clear()
            
            # Перезагружаем конфигурацию
            self.collector.load_configuration()
            
            if not self.collector.connections:
                logger.warning("⚠️ No PLCs configured")
                collector_status.connected = False
                collector_status.running = False
                return False
            
            # Переподключаемся
            for plc_id, conn in self.collector.connections.items():
                logger.info(f"🔌 Reconnecting to PLC '{conn.name}'...")
                conn.client.connect()
                collector_status.connected = conn.client.connected
                collector_status.plc_name = conn.name
            
            # Перезапускаем цикл опроса
            self.collector.running = True
            self.collector._thread = threading.Thread(
                target=self.collector._run_loop, 
                daemon=True
            )
            self.collector._thread.start()
            
            collector_status.running = True
            logger.info("✅ Collector restarted")
            return True
    
    def check_restart_request(self) -> bool:
        """
        Проверить и обработать запрос на перезапуск.
        
        Returns:
            True если был выполнен перезапуск
        """
        if collector_status.clear_restart_request():
            return self.restart()
        return False
    
    def update_connection_status(self):
        """Обновить статус подключения из текущих соединений"""
        with self._lock:
            if self.collector and self.collector.running:
                for conn in self.collector.connections.values():
                    collector_status.connected = conn.client.connected
                    break
            else:
                collector_status.connected = False
    
    def get_status(self) -> Dict[str, Any]:
        """Получить полный статус"""
        with self._lock:
            result = collector_status.to_dict()
            
            if self.collector:
                result["plc_count"] = len(self.collector.connections)
                result["buffer_size"] = len(self.collector.buffer)
            else:
                result["plc_count"] = 0
                result["buffer_size"] = 0
            
            return result

