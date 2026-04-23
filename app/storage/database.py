from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from app.config.settings import DATABASE_URL
from app.storage.models import Base


import logging
logger = logging.getLogger(__name__)
logger.info(f"Creating database engine with URL: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# SQLite-specific optimizations
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL")       # concurrent reads during writes
        cur.execute("PRAGMA cache_size = -65536")      # 64 MB page cache
        cur.execute("PRAGMA synchronous = NORMAL")     # safe + faster writes (WAL-compatible)
        cur.execute("PRAGMA mmap_size = 134217728")    # 128 MB memory-mapped I/O
        cur.execute("PRAGMA temp_store = MEMORY")      # temp tables in RAM
        cur.close()

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _run_migrations():
    """Выполнение миграций для существующей БД"""
    inspector = inspect(engine)
    
    # Проверяем существование таблицы tags
    if 'tags' not in inspector.get_table_names():
        return  # Таблица будет создана через create_all
    
    # Получаем существующие колонки
    columns = [col['name'] for col in inspector.get_columns('tags')]
    
    # Миграция: добавление bit_number если отсутствует
    if 'bit_number' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tags ADD COLUMN bit_number INTEGER DEFAULT 0"))
            conn.commit()
        logger.info("Migration: added 'bit_number' column to tags table")
    
    # Миграция: добавление memory_area если отсутствует
    if 'memory_area' not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tags ADD COLUMN memory_area VARCHAR(10) DEFAULT 'DB'"))
            conn.commit()
        logger.info("Migration: added 'memory_area' column to tags table")
    
    # Миграция: обновление уникального индекса для включения bit_number
    indexes = inspector.get_indexes('tags')
    index_names = [idx['name'] for idx in indexes]
    
    # Если старый индекс существует, удаляем его и создаём новый
    if 'ix_tag_plc_address' in index_names and 'ix_tag_plc_address_bit' not in index_names:
        with engine.connect() as conn:
            conn.execute(text("DROP INDEX IF EXISTS ix_tag_plc_address"))
            conn.execute(text("CREATE UNIQUE INDEX ix_tag_plc_address_bit ON tags (plc_id, db_number, start_address, bit_number)"))
            conn.commit()
        logger.info("Migration: updated unique index to include bit_number")


def init_db():
    """Создание всех таблиц в БД и выполнение миграций"""
    _run_migrations()
    if DATABASE_URL.startswith("sqlite"):
        _init_sqlite_autovacuum()
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def _init_sqlite_autovacuum():
    """Включает INCREMENTAL auto_vacuum. Для существующих БД выполняет разовый VACUUM."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA auto_vacuum")).fetchone()
        if result and result[0] == 0:  # 0 = NONE (не включён)
            conn.execute(text("PRAGMA auto_vacuum = INCREMENTAL"))
            conn.commit()
            logger.info("SQLite: auto_vacuum = NONE detected — running VACUUM to activate INCREMENTAL mode")
            # VACUUM нельзя выполнить внутри транзакции — используем raw DBAPI
            raw = conn.connection
            raw.isolation_level = None
            raw.execute("VACUUM")
            raw.isolation_level = ""
            logger.info("SQLite: VACUUM completed, INCREMENTAL auto_vacuum activated")


def drop_db():
    """Удаление всех таблиц (осторожно!)"""
    Base.metadata.drop_all(bind=engine)
    logger.info("Database dropped")


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Контекстный менеджер для работы с сессией.
    
    Использование:
        with get_session() as session:
            session.query(...)
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Генератор сессии для FastAPI Depends.
    
    Использование:
        @app.get("/")
        def read(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
