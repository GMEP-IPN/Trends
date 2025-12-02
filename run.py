"""
Точка входа для запуска сервиса сбора данных.

Использование:
    python run.py              - запуск сервиса сбора
    python run.py --init-db    - инициализация БД
    python run.py --demo       - добавить демо-данные и запустить
"""
import sys
import signal
from app.storage import init_db, get_session, PLC, Tag
from app.services import collector


def add_demo_config():
    """Добавление демо-конфигурации для тестирования с plcsim.py"""
    with get_session() as session:
        # Проверяем, есть ли уже ПЛК
        existing = session.query(PLC).filter(PLC.name == "SimPLC").first()
        if existing:
            print("ℹ️ Demo configuration already exists")
            return
        
        # Создаём симулятор ПЛК
        plc = PLC(
            name="SimPLC",
            ip_address="127.0.0.1",
            tcp_port=2000,
            rack=0,
            slot=1,
            is_active=True
        )
        session.add(plc)
        session.flush()
        
        # Создаём тег для чтения INT из DB1.DBW2 (как в plcsim.py)
        tag = Tag(
            plc_id=plc.id,
            name="Counter",
            description="Test counter from simulator",
            db_number=1,
            start_address=2,
            data_type="int",
            data_size=2,
            poll_interval_ms=1000,
            is_active=True
        )
        session.add(tag)
        
        print("✅ Demo configuration added:")
        print(f"   PLC: {plc.name} ({plc.ip_address}:{plc.tcp_port})")
        print(f"   Tag: {tag.name} (DB{tag.db_number}.DBW{tag.start_address})")


def signal_handler(sig, frame):
    """Обработчик сигнала остановки"""
    print("\n⚠️ Interrupt received, stopping...")
    collector.stop()
    sys.exit(0)


def main():
    args = sys.argv[1:]
    
    # Инициализация БД
    if "--init-db" in args or "--demo" in args:
        print("🗄️ Initializing database...")
        init_db()
    
    # Добавление демо-данных
    if "--demo" in args:
        add_demo_config()
    
    # Если только инициализация - выходим
    if "--init-db" in args and "--demo" not in args:
        print("✅ Database initialized. Run without --init-db to start collector.")
        return
    
    # Регистрируем обработчик Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Запускаем сервис
    collector.start()
    
    if not collector.running:
        print("❌ Failed to start collector. Check configuration.")
        return
    
    print("\n" + "="*50)
    print("📊 Collector is running. Press Ctrl+C to stop.")
    print("="*50 + "\n")
    
    # Держим главный поток
    try:
        while collector.running:
            signal.pause() if hasattr(signal, 'pause') else __import__('time').sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()


if __name__ == "__main__":
    main()
