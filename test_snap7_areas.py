"""Test snap7 server areas"""
import ctypes
import time
from snap7.server import Server, SrvArea
from snap7.client import Client
from snap7.type import Areas
from snap7 import util

# Создаём буферы
db_data = (ctypes.c_ubyte * 100)()
pe_data = (ctypes.c_ubyte * 100)()  # Inputs
pa_data = (ctypes.c_ubyte * 100)()  # Outputs
mk_data = (ctypes.c_ubyte * 100)()  # Markers

# Записываем тестовые значения
util.set_real(db_data, 0, 123.45)
util.set_real(pe_data, 0, 220.0)
util.set_real(pa_data, 0, 1500.0)
util.set_real(mk_data, 0, 760.0)

# Запускаем сервер
srv = Server()
srv.register_area(SrvArea.DB, 1, db_data)
srv.register_area(SrvArea.PE, 0, pe_data)
srv.register_area(SrvArea.PA, 0, pa_data)
srv.register_area(SrvArea.MK, 0, mk_data)
srv.start(2001)
print('Server started on port 2001')

time.sleep(1)

# Подключаемся клиентом
client = Client()
client.connect('127.0.0.1', 0, 1, 2001)
print('Client connected')

# Читаем данные
try:
    # DB
    raw = client.db_read(1, 0, 4)
    val = util.get_real(raw, 0)
    print(f'DB1.0 = {val}')
    
    # PE (Inputs) - через read_area
    raw = client.read_area(Areas.PE, 0, 0, 4)
    val = util.get_real(raw, 0)
    print(f'I0 (PE) = {val}')
    
    # PA (Outputs)
    raw = client.read_area(Areas.PA, 0, 0, 4)
    val = util.get_real(raw, 0)
    print(f'Q0 (PA) = {val}')
    
    # MK (Markers)
    raw = client.read_area(Areas.MK, 0, 0, 4)
    val = util.get_real(raw, 0)
    print(f'M0 (MK) = {val}')
    
except Exception as e:
    print(f'Error: {e}')

client.disconnect()
srv.stop()
srv.destroy()
print('Done')

