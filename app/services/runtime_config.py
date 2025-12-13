"""
Runtime configuration - настройки времени выполнения.
Используется для передачи режима работы между модулями.
"""
from dataclasses import dataclass
from typing import Optional
import threading


@dataclass
class RuntimeConfig:
    """Thread-safe runtime configuration"""
    _lock: threading.Lock = None
    _simulate_mode: bool = False
    _simulate_ab_ip: Optional[str] = None  # IP для симуляции AB PLC
    
    def __post_init__(self):
        self._lock = threading.Lock()
    
    @property
    def simulate_mode(self) -> bool:
        with self._lock:
            return self._simulate_mode
    
    @simulate_mode.setter
    def simulate_mode(self, value: bool):
        with self._lock:
            self._simulate_mode = value
    
    @property
    def simulate_ab_ip(self) -> Optional[str]:
        with self._lock:
            return self._simulate_ab_ip
    
    @simulate_ab_ip.setter
    def simulate_ab_ip(self, value: Optional[str]):
        with self._lock:
            self._simulate_ab_ip = value


# Singleton instance
runtime_config = RuntimeConfig()


