"""
Потокобезопасный статус коллектора.
Вынесен в отдельный модуль для избежания циклических импортов.
"""
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


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
    _plc_statuses: Dict[int, bool] = field(default_factory=dict)  # plc_id -> connected
    _plc_errors: Dict[int, str] = field(default_factory=dict)  # plc_id -> error message
    
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
    
    def set_plc_status(self, plc_id: int, connected: bool, error: Optional[str] = None):
        """Установить статус подключения для конкретного PLC"""
        with self._lock:
            self._plc_statuses[plc_id] = connected
            if error:
                self._plc_errors[plc_id] = error
            elif connected:
                # Очищаем ошибку только при УСПЕШНОМ подключении
                self._plc_errors.pop(plc_id, None)
            # Если connected=False и error=None, сохраняем существующую ошибку (не создаём новую)
    
    def get_plc_status(self, plc_id: int) -> Optional[bool]:
        """Получить статус подключения для конкретного PLC"""
        with self._lock:
            return self._plc_statuses.get(plc_id)
    
    def get_plc_error(self, plc_id: int) -> Optional[str]:
        """Получить сообщение об ошибке для конкретного PLC"""
        with self._lock:
            return self._plc_errors.get(plc_id)
    
    def get_all_errors(self) -> Dict[int, str]:
        """Получить все ошибки PLC"""
        with self._lock:
            return dict(self._plc_errors)
    
    def clear_plc_statuses(self):
        """Очистить все статусы PLC"""
        with self._lock:
            self._plc_statuses.clear()
            self._plc_errors.clear()

    def remove_plc(self, plc_id: int):
        """Удалить статус и ошибку конкретного PLC (вызывается при деактивации/удалении)."""
        with self._lock:
            self._plc_errors.pop(plc_id, None)
            self._plc_statuses.pop(plc_id, None)


# Глобальный потокобезопасный статус
collector_status = CollectorStatus()

