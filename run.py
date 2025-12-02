"""
Trends Collector - Точка входа

Использование:
    python run.py                    - Запуск сбора данных + веб-интерфейс
    python run.py --simulate         - Запуск в режиме симуляции
    python run.py --status           - Статус системы
    
ПЛК и теги настраиваются через веб-интерфейс: http://127.0.0.1:8000
"""
import sys
import signal
import argparse
import threading
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.config.config_loader import load_config, setup_logging, get_logger
from app.storage import init_db, get_session, PLC, Tag, TrendData
from app.services.collector_manager import CollectorManager, collector_status


# Глобальный флаг для остановки симулятора
_simulator_running = False


def run_simulator():
    """Запуск симулятора в текущем потоке"""
    global _simulator_running
    
    import ctypes
    import time
    import random
    import math
    from snap7.server import Server, SrvArea
    from snap7 import util
    
    logger = get_logger()
    
    # Параметры симуляции
    base_temp = 22.0
    base_humidity = 45.0
    temperature = base_temp
    humidity = base_humidity
    tick = 0
    
    # Генераторы для дополнительных адресов (плавные случайные значения)
    extra_values = {}  # address -> current_value
    
    db_size = 2000
    db_data = (ctypes.c_ubyte * db_size)()
    
    srv = Server()
    srv.register_area(SrvArea.DB, 1, db_data)
    srv.start(2000)
    
    logger.info("🏠 Room Simulator started on localhost:2000")
    logger.info("   DB1.0: Temperature, DB1.4: Humidity")
    logger.info("   Other addresses: random values 30-70")
    
    _simulator_running = True
    
    try:
        while _simulator_running:
            tick += 1
            
            # Суточные колебания + шум
            daily_variation = 2.0 * math.sin(tick * 0.01)
            noise = random.uniform(-0.3, 0.3)
            
            # Плавное изменение температуры (адрес 0)
            target = base_temp + daily_variation
            temperature += (target - temperature) * 0.05 + noise
            temperature = max(15.0, min(35.0, temperature))
            
            # Влажность (адрес 4)
            humidity_target = 45.0 - (temperature - 22.0) * 2
            humidity += (humidity_target - humidity) * 0.1 + random.uniform(-1, 1)
            humidity = max(20.0, min(80.0, humidity))
            
            # Записываем основные значения в DB1
            util.set_real(db_data, 0, round(temperature, 2))
            util.set_real(db_data, 4, round(humidity, 2))
            
            # Заполняем ВСЕ адреса случайными значениями (30-70)
            # Чтобы любой тег (даже с нестандартным адресом) получал данные
            for addr in range(0, 200, 4):  # адреса 0, 4, 8, 12, ... 196
                # Пропускаем адреса 0 и 4 - они уже заполнены
                if addr == 0 or addr == 4:
                    continue
                    
                if addr not in extra_values:
                    extra_values[addr] = random.uniform(30, 70)
                
                # Плавное изменение значения
                extra_values[addr] += random.uniform(-1, 1)
                extra_values[addr] = max(30, min(70, extra_values[addr]))
                
                util.set_real(db_data, addr, round(extra_values[addr], 2))
            
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Simulator error: {e}")
    finally:
        srv.destroy()
        logger.info("🏠 Room Simulator stopped")


def show_status():
    """Показать статус системы"""
    # Инициализируем БД если нужно
    init_db()
    
    print("\n" + "="*60)
    print("📊 SYSTEM STATUS")
    print("="*60)
    
    with get_session() as session:
        plc_count = session.query(PLC).filter(PLC.is_active == True).count()
        tag_count = session.query(Tag).filter(Tag.is_active == True).count()
        data_count = session.query(TrendData).count()
        
        # Последняя запись
        last_record = session.query(TrendData).order_by(
            TrendData.timestamp.desc()
        ).first()
        
        print(f"\n  PLCs (active):     {plc_count}")
        print(f"  Tags (active):     {tag_count}")
        print(f"  Trend records:     {data_count}")
        
        if last_record:
            print(f"  Last record:       {last_record.timestamp}")
            print(f"  Last value:        {last_record.value}")
        
        # Список ПЛК
        plcs = session.query(PLC).filter(PLC.is_active == True).all()
        if plcs:
            print(f"\n  PLCs:")
            for plc in plcs:
                tags = session.query(Tag).filter(Tag.plc_id == plc.id, Tag.is_active == True).count()
                print(f"    - {plc.name}: {plc.ip_address}:{plc.tcp_port} ({tags} tags)")
    
    print("\n" + "="*60)
    print("💡 Configure PLCs via web interface: http://127.0.0.1:8000")
    print("="*60 + "\n")


def run_collector(config, simulate=False):
    """Запуск коллектора с веб-интерфейсом"""
    global _simulator_running
    
    logger = get_logger()
    
    # Инициализируем БД
    logger.info("📦 Initializing database...")
    init_db()
    
    # Запуск симулятора в отдельном потоке
    if simulate:
        logger.info("🚀 Starting in SIMULATION mode...")
        simulator_thread = threading.Thread(target=run_simulator, daemon=True)
        simulator_thread.start()
        
        # Даём симулятору время запуститься
        import time
        time.sleep(2)
        
        # Создаём SimPLC в БД если его нет
        with get_session() as session:
            sim_plc = session.query(PLC).filter(PLC.name == "SimPLC").first()
            if not sim_plc:
                logger.info("📝 Creating SimPLC for simulation...")
                sim_plc = PLC(
                    name="SimPLC",
                    ip_address="127.0.0.1",
                    tcp_port=2000,
                    rack=0,
                    slot=1,
                    is_active=True
                )
                session.add(sim_plc)
                session.flush()
                
                # Добавляем теги симулятора
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="RoomTemperature",
                    description="Температура в комнате",
                    db_number=1,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="RoomHumidity",
                    description="Влажность в комнате",
                    db_number=1,
                    start_address=4,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                logger.info("✅ SimPLC created with 2 tags")
    
    # Запуск веб-сервера в отдельном потоке
    def run_web():
        import uvicorn
        from app.api.server import app
        uvicorn.run(
            app, 
            host=config.api_host, 
            port=config.api_port, 
            log_level="warning"
        )
    
    logger.info(f"🌐 Starting web server at http://{config.api_host}:{config.api_port}")
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Используем CollectorManager вместо прямой работы с CollectorService
    manager = CollectorManager(
        flush_interval_sec=config.flush_interval_sec
    )
    
    def signal_handler(sig, frame):
        global _simulator_running
        logger.info("Interrupt received, stopping...")
        _simulator_running = False
        manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    manager.start()
    
    mode = "SIMULATION" if simulate else "PRODUCTION"
    
    print("\n" + "="*60)
    print(f"📊 Trends Collector [{mode}]")
    print(f"🌐 Web interface: http://{config.api_host}:{config.api_port}")
    print(f"⌨️  Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    try:
        while True:
            import time
            time.sleep(1)
            
            # Обновляем статус подключения
            manager.update_connection_status()
            
            # Проверяем запрос на перезапуск (логика теперь в CollectorManager)
            manager.check_restart_request()
                
    except KeyboardInterrupt:
        pass
    finally:
        _simulator_running = False
        manager.stop()


def main():
    parser = argparse.ArgumentParser(
        description='Trends Collector - Сбор данных с ПЛК Siemens S7',
        epilog='ПЛК и теги настраиваются через веб-интерфейс: http://127.0.0.1:8000'
    )
    parser.add_argument('--simulate', '-s', action='store_true',
                        help='Запуск в режиме симуляции (встроенный симулятор)')
    parser.add_argument('--status', action='store_true',
                        help='Показать статус системы')
    parser.add_argument('--config', default='config.yaml',
                        help='Путь к файлу конфигурации')
    
    args = parser.parse_args()
    
    # Загружаем конфигурацию
    try:
        config = load_config(args.config)
        setup_logging(config)
    except FileNotFoundError:
        print(f"❌ Config file not found: {args.config}")
        print("   Create config.yaml or specify path with --config")
        sys.exit(1)
    
    # Выполняем команду
    if args.status:
        show_status()
    else:
        run_collector(config, simulate=args.simulate)


if __name__ == "__main__":
    main()
