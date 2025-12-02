"""
Trends Collector - Точка входа

Использование:
    python run.py                    - Запуск сбора данных
    python run.py --simulate         - Запуск в режиме симуляции (встроенный симулятор)
    python run.py --web              - Запуск веб-интерфейса
    python run.py --simulate --web   - Симуляция + веб-интерфейс
    python run.py --init             - Инициализация БД из config.yaml
    python run.py --test-connection  - Проверка подключения к ПЛК
    python run.py --list-tags        - Показать настроенные теги
    python run.py --status           - Статус системы
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
from app.services.collector_service import CollectorService


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
    
    db_size = 2000
    db_data = (ctypes.c_ubyte * db_size)()
    
    srv = Server()
    srv.register_area(SrvArea.DB, 1, db_data)
    srv.start(2000)
    
    logger.info("🏠 Room Simulator started on localhost:2000")
    
    _simulator_running = True
    
    try:
        while _simulator_running:
            tick += 1
            
            # Суточные колебания + шум
            daily_variation = 2.0 * math.sin(tick * 0.01)
            noise = random.uniform(-0.3, 0.3)
            
            # Плавное изменение температуры
            target = base_temp + daily_variation
            temperature += (target - temperature) * 0.05 + noise
            temperature = max(15.0, min(35.0, temperature))
            
            # Влажность
            humidity_target = 45.0 - (temperature - 22.0) * 2
            humidity += (humidity_target - humidity) * 0.1 + random.uniform(-1, 1)
            humidity = max(20.0, min(80.0, humidity))
            
            # Записываем в DB1
            util.set_real(db_data, 0, round(temperature, 2))
            util.set_real(db_data, 4, round(humidity, 2))
            
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Simulator error: {e}")
    finally:
        srv.destroy()
        logger.info("🏠 Room Simulator stopped")


def init_from_config(config):
    """Инициализация БД из config.yaml"""
    logger = get_logger()
    logger.info("Initializing database from config.yaml...")
    
    # Создаём таблицы
    init_db()
    
    with get_session() as session:
        for plc_cfg in config.plcs:
            if not plc_cfg.enabled:
                logger.info(f"  Skipping disabled PLC: {plc_cfg.name}")
                continue
            
            # Проверяем, есть ли уже такой ПЛК
            existing_plc = session.query(PLC).filter(PLC.name == plc_cfg.name).first()
            
            if existing_plc:
                logger.info(f"  Updating PLC: {plc_cfg.name}")
                existing_plc.ip_address = plc_cfg.ip
                existing_plc.tcp_port = plc_cfg.port
                existing_plc.rack = plc_cfg.rack
                existing_plc.slot = plc_cfg.slot
                existing_plc.is_active = True
                plc = existing_plc
            else:
                logger.info(f"  Creating PLC: {plc_cfg.name} ({plc_cfg.ip}:{plc_cfg.port})")
                plc = PLC(
                    name=plc_cfg.name,
                    ip_address=plc_cfg.ip,
                    tcp_port=plc_cfg.port,
                    rack=plc_cfg.rack,
                    slot=plc_cfg.slot,
                    is_active=True
                )
                session.add(plc)
                session.flush()
            
            # Добавляем/обновляем теги (проверка по адресу, т.к. он уникален)
            for tag_cfg in plc_cfg.tags:
                existing_tag = session.query(Tag).filter(
                    Tag.plc_id == plc.id,
                    Tag.db_number == tag_cfg.db,
                    Tag.start_address == tag_cfg.address
                ).first()
                
                if existing_tag:
                    logger.info(f"    Updating tag: {tag_cfg.name}")
                    existing_tag.name = tag_cfg.name
                    existing_tag.db_number = tag_cfg.db
                    existing_tag.start_address = tag_cfg.address
                    existing_tag.data_type = tag_cfg.type
                    existing_tag.data_size = tag_cfg.size
                    existing_tag.poll_interval_ms = tag_cfg.poll_ms
                    existing_tag.description = tag_cfg.description
                else:
                    logger.info(f"    Creating tag: {tag_cfg.name} (DB{tag_cfg.db}.{tag_cfg.address})")
                    tag = Tag(
                        plc_id=plc.id,
                        name=tag_cfg.name,
                        description=tag_cfg.description,
                        db_number=tag_cfg.db,
                        start_address=tag_cfg.address,
                        data_type=tag_cfg.type,
                        data_size=tag_cfg.size,
                        poll_interval_ms=tag_cfg.poll_ms,
                        is_active=True
                    )
                    session.add(tag)
    
    logger.info("Database initialized successfully!")


def test_connection(config):
    """Проверка подключения к ПЛК"""
    from app.collectors.S7Comm.siemens_s7 import PLC as S7Client
    
    logger = get_logger()
    logger.info("Testing PLC connections...")
    
    for plc_cfg in config.plcs:
        if not plc_cfg.enabled:
            continue
            
        logger.info(f"\nTesting {plc_cfg.name} ({plc_cfg.ip}:{plc_cfg.port})...")
        
        client = S7Client(
            plc_ip=plc_cfg.ip,
            tcp_port=plc_cfg.port,
            rack=plc_cfg.rack,
            slot=plc_cfg.slot,
            reconnect_delay=1
        )
        
        try:
            client.connect()
            if client.connected:
                logger.info(f"  ✅ Connected successfully!")
                
                # Пробуем прочитать первый тег
                if plc_cfg.tags:
                    tag = plc_cfg.tags[0]
                    try:
                        value = client.read_db(tag.db, tag.address, tag.size, tag.type)
                        logger.info(f"  ✅ Test read {tag.name}: {value}")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Read failed: {e}")
                
                client.disconnect()
            else:
                logger.error(f"  ❌ Connection failed")
        except Exception as e:
            logger.error(f"  ❌ Error: {e}")


def list_tags(config):
    """Показать настроенные теги"""
    print("\n" + "="*60)
    print("📋 CONFIGURED TAGS")
    print("="*60)
    
    for plc_cfg in config.plcs:
        status = "✅" if plc_cfg.enabled else "❌"
        print(f"\n{status} PLC: {plc_cfg.name} ({plc_cfg.ip}:{plc_cfg.port})")
        print(f"   Rack: {plc_cfg.rack}, Slot: {plc_cfg.slot}")
        print(f"   Tags ({len(plc_cfg.tags)}):")
        
        for tag in plc_cfg.tags:
            print(f"     - {tag.name}: DB{tag.db}.{tag.type.upper()}{tag.address} "
                  f"({tag.size}B, {tag.poll_ms}ms)")
            if tag.description:
                print(f"       {tag.description}")
    
    print("\n" + "="*60)


def show_status():
    """Показать статус системы"""
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
    
    print("\n" + "="*60)


def run_collector(config, simulate=False, web=False):
    """Запуск коллектора (опционально с симулятором и веб-интерфейсом)"""
    global _simulator_running
    
    logger = get_logger()
    simulator_thread = None
    web_thread = None
    
    # Запуск симулятора в отдельном потоке
    if simulate:
        logger.info("🚀 Starting in SIMULATION mode...")
        simulator_thread = threading.Thread(target=run_simulator, daemon=True)
        simulator_thread.start()
        
        # Даём симулятору время запуститься
        import time
        time.sleep(2)
    
    # Запуск веб-сервера в отдельном потоке
    if web:
        def run_web():
            import uvicorn
            from app.api.server import app
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
        
        logger.info("🌐 Starting web server at http://127.0.0.1:8000")
        web_thread = threading.Thread(target=run_web, daemon=True)
        web_thread.start()
        
        # Импортируем статус для обновления
        from app.api.server import collector_status
    
    collector = CollectorService(
        flush_interval_sec=config.flush_interval_sec
    )
    
    def signal_handler(sig, frame):
        global _simulator_running
        logger.info("Interrupt received, stopping...")
        _simulator_running = False
        collector.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    collector.start()
    
    if not collector.running:
        logger.error("Failed to start collector. Run --init first.")
        _simulator_running = False
        if web:
            collector_status["running"] = False
            collector_status["connected"] = False
        return
    
    # Обновляем статус для веб-интерфейса
    if web:
        collector_status["running"] = True
        # Проверяем подключение
        for conn in collector.connections.values():
            collector_status["connected"] = conn.client.connected
            collector_status["plc_name"] = conn.name
            break
    
    mode_parts = []
    if simulate:
        mode_parts.append("SIMULATION")
    if web:
        mode_parts.append("WEB")
    mode = " + ".join(mode_parts) if mode_parts else "PRODUCTION"
    
    print("\n" + "="*50)
    print(f"📊 Collector running [{mode}]. Press Ctrl+C to stop.")
    if web:
        print(f"🌐 Open http://127.0.0.1:8000 in your browser")
    print("="*50 + "\n")
    
    try:
        while collector.running:
            import time
            time.sleep(1)
            
            # Обновляем статус подключения для веб-интерфейса
            if web:
                for conn in collector.connections.values():
                    collector_status["connected"] = conn.client.connected
                    break
    except KeyboardInterrupt:
        pass
    finally:
        _simulator_running = False
        if web:
            collector_status["running"] = False
            collector_status["connected"] = False
        collector.stop()


def main():
    parser = argparse.ArgumentParser(
        description='Trends Collector - Сбор данных с ПЛК Siemens S7'
    )
    parser.add_argument('--init', action='store_true',
                        help='Инициализация БД из config.yaml')
    parser.add_argument('--simulate', '-s', action='store_true',
                        help='Запуск в режиме симуляции (встроенный симулятор)')
    parser.add_argument('--web', '-w', action='store_true',
                        help='Запуск веб-интерфейса')
    parser.add_argument('--test-connection', action='store_true',
                        help='Проверка подключения к ПЛК')
    parser.add_argument('--list-tags', action='store_true',
                        help='Показать настроенные теги')
    parser.add_argument('--status', action='store_true',
                        help='Статус системы')
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
    
    logger = get_logger()
    
    # Выполняем команду
    if args.init:
        init_from_config(config)
    elif args.test_connection:
        test_connection(config)
    elif args.list_tags:
        list_tags(config)
    elif args.status:
        show_status()
    else:
        run_collector(config, simulate=args.simulate, web=args.web)


if __name__ == "__main__":
    main()
