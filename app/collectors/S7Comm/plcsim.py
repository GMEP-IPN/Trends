"""
Симулятор ПЛК с датчиками помещения.
Генерирует реалистичные показания температуры, влажности и статуса оборудования.
"""
import ctypes
import time
import random
import math
from snap7.server import Server, SrvArea
from snap7 import util


class RoomSimulator:
    """Симуляция показаний датчиков комнаты"""
    
    def __init__(self):
        # Базовые значения
        self.base_temp = 22.0       # Базовая температура (°C)
        self.base_humidity = 45.0   # Базовая влажность (%)
        
        # Текущие значения
        self.temperature = self.base_temp
        self.humidity = self.base_humidity
        self.ac_running = False
        self.heater_running = False
        
        # Счётчик времени для синусоидальных колебаний
        self.tick = 0
        
        # Целевая температура (термостат)
        self.target_temp = 22.0
    
    def update(self):
        """Обновление показаний датчиков"""
        self.tick += 1
        
        # Суточные колебания температуры (синусоида ~2°C)
        daily_variation = 2.0 * math.sin(self.tick * 0.01)
        
        # Случайный шум (±0.3°C)
        noise = random.uniform(-0.3, 0.3)
        
        # Влияние кондиционера/обогревателя
        if self.ac_running:
            self.temperature -= 0.1  # Охлаждение
        elif self.heater_running:
            self.temperature += 0.1  # Нагрев
        else:
            # Стремление к базовой + суточное колебание
            target = self.base_temp + daily_variation
            self.temperature += (target - self.temperature) * 0.05
        
        # Добавляем шум
        self.temperature += noise
        
        # Ограничиваем диапазон (15-35°C)
        self.temperature = max(15.0, min(35.0, self.temperature))
        
        # Автоматика: включаем AC если жарко, обогреватель если холодно
        if self.temperature > self.target_temp + 2:
            self.ac_running = True
            self.heater_running = False
        elif self.temperature < self.target_temp - 2:
            self.ac_running = False
            self.heater_running = True
        elif abs(self.temperature - self.target_temp) < 0.5:
            self.ac_running = False
            self.heater_running = False
        
        # Влажность зависит от температуры и AC
        humidity_base = 45.0 - (self.temperature - 22.0) * 2
        if self.ac_running:
            humidity_base -= 5  # AC сушит воздух
        
        self.humidity += (humidity_base - self.humidity) * 0.1
        self.humidity += random.uniform(-1, 1)
        self.humidity = max(20.0, min(80.0, self.humidity))
        
        return {
            'temperature': round(self.temperature, 2),
            'humidity': round(self.humidity, 2),
            'ac_running': self.ac_running,
            'heater_running': self.heater_running
        }


def main():
    db_size = 2000
    db_data = (ctypes.c_ubyte * db_size)()
    
    srv = Server()
    srv.register_area(SrvArea.DB, 1, db_data)
    
    # Старт сервера
    srv.start(2000)
    
    print("✅ Snap7 Room Simulator started on localhost:2000")
    print("="*50)
    print("📊 Simulating room sensors:")
    print("   DB1.DBD0  - Temperature (REAL, 4 bytes)")
    print("   DB1.DBD4  - Humidity (REAL, 4 bytes)")  
    print("   DB1.DBX8.0 - AC Running (BOOL)")
    print("   DB1.DBX8.1 - Heater Running (BOOL)")
    print("="*50)
    
    room = RoomSimulator()
    
    try:
        while True:
            data = room.update()
            
            # Записываем в DB1
            # Temperature: REAL at address 0 (4 bytes)
            util.set_real(db_data, 0, data['temperature'])
            
            # Humidity: REAL at address 4 (4 bytes)
            util.set_real(db_data, 4, data['humidity'])
            
            # AC Running: BOOL at address 8, bit 0
            util.set_bool(db_data, 8, 0, data['ac_running'])
            
            # Heater Running: BOOL at address 8, bit 1
            util.set_bool(db_data, 8, 1, data['heater_running'])
            
            # Вывод в консоль
            ac_status = "❄️ AC" if data['ac_running'] else "🔥 Heat" if data['heater_running'] else "⏸️ Off"
            print(f"🌡️ {data['temperature']:5.1f}°C  💧 {data['humidity']:4.1f}%  {ac_status}")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
    finally:
        srv.destroy()


if __name__ == "__main__":
    main()
