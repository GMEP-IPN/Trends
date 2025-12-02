from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from app.config.settings import DATABASE_URL
from app.storage.models import Base


# Создаём движок БД
engine = create_engine(
    DATABASE_URL,
    echo=False,  # True для отладки SQL запросов
    pool_pre_ping=True,  # Проверка соединения перед использованием
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Создание всех таблиц в БД"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")


def drop_db():
    """Удаление всех таблиц (осторожно!)"""
    Base.metadata.drop_all(bind=engine)
    print("🗑️ Database dropped")


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
