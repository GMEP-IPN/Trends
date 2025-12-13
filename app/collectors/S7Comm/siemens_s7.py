"""
Клиент для связи с ПЛК Siemens S7.
"""
import logging
import snap7
from snap7.util import (
    get_bool, get_int, get_dint, get_real,
    get_word, get_dword, get_string
)
from time import sleep
from typing import Optional, Any

logger = logging.getLogger('trends')

# Snap7 exception - may vary between versions
try:
    Snap7Exception = snap7.snap7exceptions.Snap7Exception
except AttributeError:
    # Newer versions of snap7 may use different exception hierarchy
    Snap7Exception = RuntimeError


class PLCConnectionError(Exception):
    """Ошибка подключения к ПЛК"""
    pass


class PLCReadError(Exception):
    """Ошибка чтения данных из ПЛК"""
    pass


class PLC:
    """
    Клиент для подключения к ПЛК Siemens S7.
    
    Attributes:
        plc_ip: IP адрес ПЛК
        tcp_port: TCP порт (102 для реального ПЛК, 2000 для симулятора)
        rack: Номер rack
        slot: Номер slot (1 для S7-1200/1500, 2 для S7-300/400)
        reconnect_delay: Задержка между попытками переподключения (сек)
        max_reconnect_attempts: Максимум попыток переподключения (0 = бесконечно)
    """
    
    def __init__(
        self, 
        plc_ip: str, 
        tcp_port: int = 102, 
        rack: int = 0, 
        slot: int = 1, 
        reconnect_delay: float = 2.0,
        max_reconnect_attempts: int = 10
    ):
        self.plc_ip = plc_ip
        self.tcp_port = tcp_port
        self.rack = rack
        self.slot = slot
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self.client = snap7.client.Client()
        self.connected = False

        # Таблица парсеров для разных типов данных
        self.parsers = {
            "int": lambda data: get_int(data, 0),
            "dint": lambda data: get_dint(data, 0),
            "real": lambda data: get_real(data, 0),
            "word": lambda data: get_word(data, 0),
            "dword": lambda data: get_dword(data, 0),
            "bool": lambda data: get_bool(data, 0, 0),
            "string": lambda data: get_string(data, 0).strip("\x00"),
        }

    def connect(self) -> bool:
        """
        Подключение к ПЛК.
        
        Returns:
            True если подключение успешно
        """
        if self.connected:
            return True
            
        try:
            logger.info(f"Connecting to {self.plc_ip}:{self.tcp_port}...")
            # Отключаемся перед новым подключением
            try:
                self.client.disconnect()
            except Exception:
                pass  # Игнорируем ошибки отключения

            # Подключаемся с указанными параметрами
            self.client.connect(self.plc_ip, self.rack, self.slot, self.tcp_port)

            # Проверяем статус соединения через API snap7
            if self.client.get_connected():
                self.connected = True
                logger.info(f"Connected to PLC at {self.plc_ip}:{self.tcp_port}")
                return True
            else:
                self.connected = False
                logger.warning(f"Connection status check failed for {self.plc_ip}:{self.tcp_port}")
                return False
                
        except (Snap7Exception, RuntimeError) as e:
            logger.warning(f"Connection failed to {self.plc_ip}:{self.tcp_port}: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.plc_ip}:{self.tcp_port}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от ПЛК"""
        if self.connected:
            try:
                self.client.disconnect()
                logger.info(f"Disconnected from PLC {self.plc_ip}:{self.tcp_port}")
            except (Snap7Exception, RuntimeError) as e:
                logger.warning(f"Warning during disconnect: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during disconnect: {e}")
            finally:
                self.connected = False

    def ensure_connection(self, timeout_attempts: Optional[int] = None) -> bool:
        """
        Убедиться, что соединение установлено. При необходимости переподключиться.
        
        Args:
            timeout_attempts: Максимум попыток (None = использовать значение по умолчанию)
            
        Returns:
            True если соединение установлено
            
        Raises:
            PLCConnectionError: Если не удалось подключиться после всех попыток
        """
        if self.connected:
            return True
        
        max_attempts = timeout_attempts if timeout_attempts is not None else self.max_reconnect_attempts
        attempts = 0
        
        logger.info(f"Reconnecting to PLC {self.plc_ip}:{self.tcp_port}...")
        
        while not self.connected:
            attempts += 1
            
            if self.connect():
                return True
            
            # Проверяем лимит попыток (0 = бесконечно)
            if max_attempts > 0 and attempts >= max_attempts:
                error_msg = f"Failed to connect to {self.plc_ip}:{self.tcp_port} after {attempts} attempts"
                logger.error(f"{error_msg}")
                raise PLCConnectionError(error_msg)
            
            logger.info(f"   Attempt {attempts}/{max_attempts if max_attempts > 0 else '∞'}, retrying in {self.reconnect_delay}s...")
            sleep(self.reconnect_delay)
        
        return True

    def read_db(self, db_number: int, start: int, size: int, type_data: str, bit_number: int = 0) -> Any:
        """
        Чтение данных из DB с автопереподключением.
        
        Args:
            db_number: Номер DB
            start: Начальный адрес (байт)
            size: Размер данных (байт)
            type_data: Тип данных (int, dint, real, word, dword, bool, string)
            bit_number: Номер бита (0-7, только для bool)
            
        Returns:
            Значение указанного типа
            
        Raises:
            ValueError: Если тип данных не поддерживается
            PLCReadError: Если не удалось прочитать данные
        """
        if type_data not in self.parsers:
            raise ValueError(f"Unsupported data type: {type_data}. Supported: {list(self.parsers.keys())}")

        try:
            self.ensure_connection()
        except PLCConnectionError as e:
            raise PLCReadError(f"Cannot read DB{db_number}.{start}: {e}")

        try:
            raw = self.client.db_read(db_number, start, size)
            # Для bool используем указанный номер бита
            if type_data == "bool":
                return get_bool(raw, 0, bit_number)
            return self.parsers[type_data](raw)

        except (Snap7Exception, RuntimeError) as e:
            logger.warning(f"Read failed (DB{db_number}.{start}): {e}")
            # Не сбрасываем статус при первой ошибке - может быть временной
            # self.connected = False

            # Вторая попытка после переподключения
            try:
                self.ensure_connection(timeout_attempts=3)
                raw = self.client.db_read(db_number, start, size)
                if type_data == "bool":
                    return get_bool(raw, 0, bit_number)
                return self.parsers[type_data](raw)
            except (PLCConnectionError, Snap7Exception, RuntimeError) as retry_err:
                # Сбрасываем статус только если вторая попытка тоже провалилась
                self.connected = False
                raise PLCReadError(f"Failed to read DB{db_number}.{start} after retry: {retry_err}")
        
        except Exception as e:
            logger.error(f"Unexpected read error (DB{db_number}.{start}): {e}")
            self.connected = False
            raise PLCReadError(f"Unexpected error reading DB{db_number}.{start}: {e}")


if __name__ == "__main__":
    # Тестовый запуск
    plc = PLC("127.0.0.1", 2000, 0, 1)
    try:
        value_real = plc.read_db(1, 0, 4, "real")
        print("REAL:", value_real)
    except (PLCConnectionError, PLCReadError) as e:
        print(f"Error: {e}")
    finally:
        plc.disconnect()
