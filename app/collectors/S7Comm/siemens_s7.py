import snap7
from snap7.util import (
    get_bool, get_int, get_dint, get_real,
    get_word, get_dword, get_string
)
from time import sleep


class PLC:
    def __init__(self, plc_ip, tcp_port, rack, slot, reconnect_delay=2):
        self.plc_ip = plc_ip
        self.tcp_port = tcp_port
        self.rack = rack
        self.slot = slot
        self.reconnect_delay = reconnect_delay

        self.client = snap7.client.Client()
        self.connected = False

        # Таблица функций
        self.parsers = {
            "int": lambda data: get_int(data, 0),
            "dint": lambda data: get_dint(data, 0),
            "real": lambda data: get_real(data, 0),
            "word": lambda data: get_word(data, 0),
            "dword": lambda data: get_dword(data, 0),
            "bool": lambda data: get_bool(data, 0, 0),  # DBX0.0
            "string": lambda data: get_string(data, 0).strip("\x00"),
        }

    def connect(self):
        if not self.connected:
            try:
                print(f"🔌 Connecting to {self.plc_ip}:{self.tcp_port}...")
                self.client.connect(self.plc_ip, self.rack, self.slot, tcp_port=self.tcp_port)
                
                # Проверяем реальное соединение тестовым чтением
                try:
                    self.client.db_read(1, 0, 1)  # Читаем 1 байт из DB1
                    self.connected = True
                    print(f"✅ Connected to PLC at {self.plc_ip}:{self.tcp_port}")
                except Exception as read_err:
                    self.connected = False
                    print(f"⚠️ Connection test failed to {self.plc_ip}:{self.tcp_port}: {read_err}")
                    self.client.disconnect()
            except Exception as e:
                print(f"⚠️ Connection failed to {self.plc_ip}:{self.tcp_port}: {e}")
                self.connected = False

    def disconnect(self):
        if self.connected:
            try:
                self.client.disconnect()
                print("❌ Disconnected from PLC")
            except:
                pass
            finally:
                self.connected = False

    def ensure_connection(self):
        if not self.connected or not self.client.get_connected():
            print("🔄 Reconnecting to PLC...")
            self.connected = False
            while not self.connected:
                self.connect()
                if not self.connected:
                    sleep(self.reconnect_delay)

    def read_db(self, db_number, start, size, type_data):
        """
        Чтение DB с автопереподключением и автоматическим выбором парсера.
        """
        self.ensure_connection()

        if type_data not in self.parsers:
            raise ValueError(f"❌ Unsupported type: {type_data}")

        try:
            raw = self.client.db_read(db_number, start, size)
            return self.parsers[type_data](raw)

        except Exception as e:
            print(f"⚠️ Read failed: {e}")
            self.connected = False
            self.ensure_connection()

            # вторая попытка
            raw = self.client.db_read(db_number, start, size)
            return self.parsers[type_data](raw)


if __name__ == "__main__":
    plc = PLC("127.0.0.1", 2000, 0, 1)
    value_int = plc.read_db(1, 2, 2, "int")
    print("INT:", value_int)

