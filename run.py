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

from app import __version__
from app.config.config_loader import load_config, setup_logging, get_logger
from app.storage import init_db, get_session, PLC, Tag, TrendData
from app.services.collector_manager import CollectorManager, collector_status


# Глобальный флаг для остановки симулятора
_simulator_running = False


def run_simulator(port: int = 2000, db_size: int = 2000, update_interval: float = 1.0):
    """
    Запуск симулятора в текущем потоке.
    Поддерживает все области памяти S7: DB, I, Q, M
    
    Args:
        port: Порт симулятора (из config.yaml)
        db_size: Размер DB в байтах (из config.yaml)
        update_interval: Интервал обновления в секундах (из config.yaml)
    """
    global _simulator_running
    
    import ctypes
    import time
    import random
    import math
    from snap7.server import Server, SrvArea
    from snap7 import util
    
    logger = get_logger()
    
    # Размеры областей памяти
    area_size = 256  # байт для I, Q, M
    
    # Параметры симуляции
    base_temp = 22.0
    base_humidity = 45.0
    temperature = base_temp
    humidity = base_humidity
    pressure = 760.0  # мм рт.ст.
    tick = 0
    
    # Генераторы для дополнительных адресов (плавные случайные значения)
    extra_values = {}  # (area, address) -> current_value
    
    # Создаём буферы для всех областей памяти S7
    db_data = (ctypes.c_ubyte * db_size)()
    input_data = (ctypes.c_ubyte * area_size)()   # I (Inputs)
    output_data = (ctypes.c_ubyte * area_size)()  # Q (Outputs)
    marker_data = (ctypes.c_ubyte * area_size)()  # M (Markers)
    timer_data = (ctypes.c_ubyte * area_size)()   # T (Timers)
    counter_data = (ctypes.c_ubyte * area_size)() # C (Counters)
    
    srv = Server()
    # Регистрируем все области памяти S7
    srv.register_area(SrvArea.DB, 1, db_data)      # DB1
    srv.register_area(SrvArea.PE, 0, input_data)   # I (Inputs) - index=0
    srv.register_area(SrvArea.PA, 0, output_data)  # Q (Outputs) - index=0
    srv.register_area(SrvArea.MK, 0, marker_data)  # M (Markers) - index=0
    srv.register_area(SrvArea.TM, 0, timer_data)   # T (Timers) - index=0
    srv.register_area(SrvArea.CT, 0, counter_data) # C (Counters) - index=0
    srv.start(port)
    
    logger.info(f"Room Simulator started on localhost:{port}")
    logger.info("   DB1: Temperature, Humidity")
    logger.info("   I0: InputVoltage, Q0: OutputPower, M0: Pressure")
    logger.info("   T0: Uptime, C0: CycleCount")
    
    _simulator_running = True
    
    try:
        while _simulator_running:
            tick += 1
            
            # Суточные колебания + шум
            daily_variation = 2.0 * math.sin(tick * 0.01)
            noise = random.uniform(-0.3, 0.3)
            
            # === DB1: Temperature & Humidity ===
            target = base_temp + daily_variation
            temperature += (target - temperature) * 0.05 + noise
            temperature = max(15.0, min(35.0, temperature))
            
            humidity_target = 45.0 - (temperature - 22.0) * 2
            humidity += (humidity_target - humidity) * 0.1 + random.uniform(-1, 1)
            humidity = max(20.0, min(80.0, humidity))
            
            util.set_real(db_data, 0, round(temperature, 2))
            util.set_real(db_data, 4, round(humidity, 2))
            
            # === I (Inputs): Voltage simulation ===
            input_voltage = 220.0 + random.uniform(-5, 5) + 10 * math.sin(tick * 0.02)
            util.set_real(input_data, 0, round(input_voltage, 2))
            
            # === Q (Outputs): Power output ===
            output_power = max(0, temperature * 100 + random.uniform(-50, 50))
            util.set_real(output_data, 0, round(output_power, 2))
            
            # === M (Markers): Pressure ===
            pressure += random.uniform(-0.5, 0.5)
            pressure = max(740, min(780, pressure))
            util.set_real(marker_data, 0, round(pressure, 2))
            
            # === T (Timers): Uptime simulation ===
            uptime = tick * update_interval  # секунды работы
            util.set_real(timer_data, 0, round(uptime, 2))
            
            # === C (Counters): Cycle counter ===
            cycle_count = float(tick % 10000)  # счётчик циклов
            util.set_real(counter_data, 0, cycle_count)
            
            # Заполняем дополнительные адреса во всех областях
            all_areas = [
                ('DB', db_data, 8, 200),       # DB1: с адреса 8 (0,4 заняты)
                ('I', input_data, 4, 64),      # DB2: с адреса 4
                ('Q', output_data, 4, 64),     # DB3: с адреса 4
                ('M', marker_data, 4, 64),     # DB4: с адреса 4
                ('T', timer_data, 4, 64),      # DB5: с адреса 4
                ('C', counter_data, 4, 64),    # DB6: с адреса 4
            ]
            
            for area_name, area_data, start_addr, end_addr in all_areas:
                for addr in range(start_addr, end_addr, 4):
                    key = (area_name, addr)
                    if key not in extra_values:
                        extra_values[key] = random.uniform(30, 70)
                    
                    extra_values[key] += random.uniform(-1, 1)
                    extra_values[key] = max(30, min(70, extra_values[key]))
                    
                    util.set_real(area_data, addr, round(extra_values[key], 2))
            
            time.sleep(update_interval)
            
    except Exception as e:
        logger.error(f"Simulator error: {e}")
    finally:
        srv.destroy()
        logger.info("Room Simulator stopped")


def show_status():
    """Показать статус системы"""
    # Инициализируем БД если нужно
    init_db()
    
    print("\n" + "="*60)
    print("SYSTEM STATUS")
    print("="*60)
    
    from app.services.trend_service import get_total_trend_count, get_global_latest_record
    
    with get_session() as session:
        plc_count = session.query(PLC).filter(PLC.is_active == True).count()
        tag_count = session.query(Tag).filter(Tag.is_active == True).count()
        
        data_count = get_total_trend_count()
        last_record = get_global_latest_record()
        
        print(f"\n  PLCs (active):     {plc_count}")
        print(f"  Tags (active):     {tag_count}")
        print(f"  Trend records:     {data_count}")
        
        if last_record:
            print(f"  Last record:       {last_record[0]}")
            print(f"  Last value:        {last_record[1]}")
        
        # Список ПЛК
        plcs = session.query(PLC).filter(PLC.is_active == True).all()
        if plcs:
            print(f"\n  PLCs:")
            for plc in plcs:
                tags = session.query(Tag).filter(Tag.plc_id == plc.id, Tag.is_active == True).count()
                print(f"    - {plc.name}: {plc.ip_address}:{plc.tcp_port} ({tags} tags)")
    
    print("\n" + "="*60)
    print("Configure PLCs via web interface: http://127.0.0.1:8000")
    print("="*60 + "\n")


def run_collector(config, simulate=False):
    """Запуск коллектора с веб-интерфейсом"""
    global _simulator_running
    
    logger = get_logger()
    
    # Устанавливаем режим симуляции глобально
    from app.services.runtime_config import runtime_config
    runtime_config.simulate_mode = simulate
    
    # Инициализируем БД
    logger.info("Initializing database...")
    init_db()
    
    # Запуск симулятора в отдельном потоке
    if simulate:
        logger.info("Starting in SIMULATION mode...")
        simulator_thread = threading.Thread(
            target=run_simulator,
            args=(config.simulator_port, config.simulator_db_size, config.simulator_update_interval),
            daemon=True
        )
        simulator_thread.start()
        
        # Даём симулятору время запуститься
        import time
        time.sleep(4)
        
        # Создаём SimPLC в БД если его нет
        with get_session() as session:
            sim_plc = session.query(PLC).filter(PLC.name == "SimPLC").first()
            if not sim_plc:
                logger.info("Creating SimPLC for simulation...")
                sim_plc = PLC(
                    name="SimPLC",
                    ip_address="127.0.0.1",
                    tcp_port=config.simulator_port,  # Используем порт из config
                    rack=0,
                    slot=1,
                    is_active=True
                )
                session.add(sim_plc)
                session.flush()
                
                # Добавляем теги симулятора для всех областей памяти
                # DB1: Temperature & Humidity
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="RoomTemperature",
                    description="Температура в комнате (DB1.REAL0)",
                    memory_area="DB",
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
                    description="Влажность в комнате (DB1.REAL4)",
                    memory_area="DB",
                    db_number=1,
                    start_address=4,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                # I (Inputs): Voltage
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="InputVoltage",
                    description="Напряжение на входе (I0)",
                    memory_area="I",
                    db_number=None,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                # Q (Outputs): Power
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="OutputPower",
                    description="Мощность на выходе (Q0)",
                    memory_area="Q",
                    db_number=None,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                # M (Markers): Pressure
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="Pressure",
                    description="Атмосферное давление (M0)",
                    memory_area="M",
                    db_number=None,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                # T (Timers): Uptime
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="Uptime",
                    description="Время работы (T0)",
                    memory_area="T",
                    db_number=None,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                # C (Counters): CycleCount
                session.add(Tag(
                    plc_id=sim_plc.id,
                    name="CycleCount",
                    description="Счётчик циклов (C0)",
                    memory_area="C",
                    db_number=None,
                    start_address=0,
                    data_type="real",
                    data_size=4,
                    poll_interval_ms=1000,
                    is_active=True
                ))
                logger.info("SimPLC created with 7 tags (DB, I, Q, M, T, C)")
            
            # Создаём SimAB (Allen-Bradley) в режиме симуляции
            sim_ab = session.query(PLC).filter(PLC.name == "SimAB").first()
            if not sim_ab:
                logger.info("Creating SimAB (Allen-Bradley) for simulation...")
                sim_ab = PLC(
                    name="SimAB",
                    plc_type="allen_bradley",
                    ip_address="127.0.0.1",  # Виртуальный IP для симуляции
                    tcp_port=44818,  # Стандартный порт EtherNet/IP
                    slot_ab=0,
                    is_active=True
                )
                session.add(sim_ab)
                session.flush()
                
                # Добавляем теги для Allen-Bradley симулятора
                session.add(Tag(
                    plc_id=sim_ab.id,
                    name="Temperature",
                    description="Simulated Temperature",
                    ab_tag_name="Temperature",
                    data_type="real",
                    poll_interval_ms=1000,
                    is_active=True
                ))
                session.add(Tag(
                    plc_id=sim_ab.id,
                    name="Pressure",
                    description="Simulated Pressure",
                    ab_tag_name="Pressure",
                    data_type="real",
                    poll_interval_ms=1000,
                    is_active=True
                ))
                session.add(Tag(
                    plc_id=sim_ab.id,
                    name="FlowRate",
                    description="Simulated Flow Rate",
                    ab_tag_name="FlowRate",
                    data_type="real",
                    poll_interval_ms=1000,
                    is_active=True
                ))
                session.add(Tag(
                    plc_id=sim_ab.id,
                    name="ProductCount",
                    description="Simulated Product Counter",
                    ab_tag_name="ProductCount",
                    data_type="dint",
                    poll_interval_ms=1000,
                    is_active=True
                ))
                session.add(Tag(
                    plc_id=sim_ab.id,
                    name="Motor_Running",
                    description="Motor Status",
                    ab_tag_name="Motor_Running",
                    data_type="bool",
                    poll_interval_ms=1000,
                    is_active=True
                ))
                logger.info("SimAB created with 5 tags")
    
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
    
    logger.info(f"Starting web server at http://{config.api_host}:{config.api_port}")
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Используем CollectorManager вместо прямой работы с CollectorService
    manager = CollectorManager(
        flush_interval_sec=config.flush_interval_sec,
        retention_days=config.retention_days,
        cleanup_interval_hours=config.cleanup_interval_hours
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
    print(f"Trends v{__version__} [{mode}]")
    print(f"Web interface: http://{config.api_host}:{config.api_port}")
    print(f"Press Ctrl+C to stop")
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
        print(f"Config file not found: {args.config}")
        print("Create config.yaml or specify path with --config")
        sys.exit(1)
    
    # Выполняем команду
    if args.status:
        show_status()
    else:
        run_collector(config, simulate=args.simulate)


if __name__ == "__main__":
    main()
