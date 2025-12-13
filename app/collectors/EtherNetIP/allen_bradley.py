"""
Клиент для связи с ПЛК Allen-Bradley через EtherNet/IP.

Поддерживаемые контроллеры:
- ControlLogix (L6x, L7x, L8x)
- CompactLogix (L1x, L2x, L3x)
- Micro800 (820, 850, 870)
"""
import logging
from time import sleep
from typing import Optional, Any, List

logger = logging.getLogger('trends')

# Пытаемся импортировать pycomm3
try:
    from pycomm3 import LogixDriver
    from pycomm3.exceptions import CommError
    PYCOMM3_AVAILABLE = True
except ImportError:
    PYCOMM3_AVAILABLE = False
    LogixDriver = None
    CommError = Exception
    logger.warning("pycomm3 not installed. Allen-Bradley support disabled. Install with: pip install pycomm3")


class ABConnectionError(Exception):
    """Ошибка подключения к ПЛК Allen-Bradley"""
    pass


class ABReadError(Exception):
    """Ошибка чтения данных из ПЛК Allen-Bradley"""
    pass


class ABClient:
    """
    Клиент для подключения к ПЛК Allen-Bradley через EtherNet/IP.
    
    Attributes:
        plc_ip: IP адрес ПЛК
        slot: Номер слота (для ControlLogix, обычно 0)
        reconnect_delay: Задержка между попытками переподключения (сек)
        max_reconnect_attempts: Максимум попыток переподключения (0 = бесконечно)
    """
    
    def __init__(
        self, 
        plc_ip: str, 
        slot: int = 0,
        reconnect_delay: float = 2.0,
        max_reconnect_attempts: int = 10
    ):
        if not PYCOMM3_AVAILABLE:
            raise ABConnectionError("pycomm3 library not installed. Run: pip install pycomm3")
        
        self.plc_ip = plc_ip
        self.slot = slot
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        
        self._driver: Optional[LogixDriver] = None
        self.connected = False

    def connect(self) -> bool:
        """
        Подключение к ПЛК.
        
        Returns:
            True если подключение успешно
        """
        if self.connected and self._driver:
            return True
        
        try:
            logger.info(f"Connecting to Allen-Bradley at {self.plc_ip} slot {self.slot}...")
            
            # Закрываем старое соединение если есть
            self.disconnect()
            
            # Создаём драйвер с указанием слота
            # Формат: "IP/slot" или просто "IP"
            path = f"{self.plc_ip}/{self.slot}" if self.slot > 0 else self.plc_ip
            self._driver = LogixDriver(path)
            self._driver.open()
            
            self.connected = True
            logger.info(f"Connected to Allen-Bradley at {self.plc_ip}")
            return True
            
        except CommError as e:
            logger.warning(f"Connection failed to {self.plc_ip}: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.plc_ip}: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от ПЛК"""
        if self._driver:
            try:
                self._driver.close()
                logger.info(f"Disconnected from Allen-Bradley {self.plc_ip}")
            except Exception as e:
                logger.warning(f"Warning during disconnect: {e}")
            finally:
                self._driver = None
                self.connected = False

    def ensure_connection(self, timeout_attempts: Optional[int] = None) -> bool:
        """
        Убедиться, что соединение установлено. При необходимости переподключиться.
        
        Args:
            timeout_attempts: Максимум попыток (None = использовать значение по умолчанию)
            
        Returns:
            True если соединение установлено
            
        Raises:
            ABConnectionError: Если не удалось подключиться после всех попыток
        """
        if self.connected and self._driver:
            return True
        
        max_attempts = timeout_attempts if timeout_attempts is not None else self.max_reconnect_attempts
        attempts = 0
        
        logger.info(f"Reconnecting to Allen-Bradley {self.plc_ip}...")
        
        while not self.connected:
            attempts += 1
            
            if self.connect():
                return True
            
            # Проверяем лимит попыток (0 = бесконечно)
            if max_attempts > 0 and attempts >= max_attempts:
                error_msg = f"Failed to connect to {self.plc_ip} after {attempts} attempts"
                logger.error(f"{error_msg}")
                raise ABConnectionError(error_msg)
            
            logger.info(f"   Attempt {attempts}/{max_attempts if max_attempts > 0 else '∞'}, retrying in {self.reconnect_delay}s...")
            sleep(self.reconnect_delay)
        
        return True

    def read_tag(self, tag_name: str) -> Any:
        """
        Чтение значения тега по имени.
        
        Args:
            tag_name: Имя тега в ПЛК (например "MyTag", "Program:MainProgram.Counter")
            
        Returns:
            Значение тега
            
        Raises:
            ABReadError: Если не удалось прочитать данные
        """
        try:
            self.ensure_connection()
        except ABConnectionError as e:
            raise ABReadError(f"Cannot read tag '{tag_name}': {e}")

        try:
            result = self._driver.read(tag_name)
            
            if result.error:
                raise ABReadError(f"Read error for tag '{tag_name}': {result.error}")
            
            return result.value

        except CommError as e:
            logger.warning(f"Read failed for tag '{tag_name}': {e}")
            
            # Пробуем переподключиться и повторить
            try:
                self.connected = False
                self.ensure_connection(timeout_attempts=3)
                result = self._driver.read(tag_name)
                
                if result.error:
                    raise ABReadError(f"Read error for tag '{tag_name}': {result.error}")
                
                return result.value
            except (ABConnectionError, CommError) as retry_err:
                self.connected = False
                raise ABReadError(f"Failed to read tag '{tag_name}' after retry: {retry_err}")
        
        except Exception as e:
            logger.error(f"Unexpected read error for tag '{tag_name}': {e}")
            self.connected = False
            raise ABReadError(f"Unexpected error reading tag '{tag_name}': {e}")

    def read_tags(self, tag_names: List[str]) -> dict:
        """
        Чтение нескольких тегов за один запрос (оптимизированно).
        
        Args:
            tag_names: Список имён тегов
            
        Returns:
            Словарь {tag_name: value}
        """
        try:
            self.ensure_connection()
        except ABConnectionError as e:
            raise ABReadError(f"Cannot read tags: {e}")

        try:
            results = self._driver.read(*tag_names)
            
            # Если читаем один тег, results будет Tag, иначе список
            if not isinstance(results, list):
                results = [results]
            
            values = {}
            for result in results:
                if result.error:
                    logger.warning(f"Error reading tag '{result.tag}': {result.error}")
                    values[result.tag] = None
                else:
                    values[result.tag] = result.value
            
            return values

        except CommError as e:
            logger.error(f"Batch read failed: {e}")
            self.connected = False
            raise ABReadError(f"Batch read failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected batch read error: {e}")
            self.connected = False
            raise ABReadError(f"Unexpected batch read error: {e}")

    def get_tag_list(self) -> List[dict]:
        """
        Получение списка всех тегов в ПЛК.
        
        Returns:
            Список словарей с информацией о тегах
        """
        try:
            self.ensure_connection()
            tags = self._driver.get_tag_list()
            return [
                {
                    'name': tag.tag_name,
                    'type': str(tag.data_type),
                    'dim': tag.dimensions if hasattr(tag, 'dimensions') else 0
                }
                for tag in tags
            ]
        except Exception as e:
            logger.error(f"Failed to get tag list: {e}")
            raise ABReadError(f"Failed to get tag list: {e}")


if __name__ == "__main__":
    # Тестовый запуск
    if not PYCOMM3_AVAILABLE:
        print("pycomm3 not installed. Run: pip install pycomm3")
    else:
        client = ABClient("192.168.1.10", slot=0)
        try:
            client.connect()
            # Пример чтения
            # value = client.read_tag("MyTag")
            # print(f"Value: {value}")
            
            # Получить список тегов
            tags = client.get_tag_list()
            for tag in tags[:10]:  # Первые 10 тегов
                print(f"  {tag['name']}: {tag['type']}")
        except (ABConnectionError, ABReadError) as e:
            print(f"Error: {e}")
        finally:
            client.disconnect()
