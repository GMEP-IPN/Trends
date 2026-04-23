"""
Сервис для работы с данными трендов.
Функции для запроса и анализа исторических данных.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
from sqlalchemy import func, text

from app.storage import get_session, Tag, TrendData
from app.storage.database import engine


def get_trend_data(
    tag_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 1000
) -> List[Tuple[datetime, float]]:
    """
    Получение данных тренда за период.
    
    Args:
        tag_id: ID тега
        start_time: Начало периода (по умолчанию - последний час)
        end_time: Конец периода (по умолчанию - сейчас)
        limit: Максимум записей
    
    Returns:
        Список кортежей (timestamp, value)
    """
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=1)
    
    with get_session() as session:
        data = session.query(TrendData.timestamp, TrendData.value).filter(
            TrendData.tag_id == tag_id,
            TrendData.timestamp >= start_time,
            TrendData.timestamp <= end_time
        ).order_by(TrendData.timestamp).limit(limit).all()
        
        return [(row.timestamp, row.value) for row in data]


def get_latest_value(tag_id: int) -> Optional[Tuple[datetime, float]]:
    """Получение последнего значения тега"""
    with get_session() as session:
        data = session.query(TrendData.timestamp, TrendData.value).filter(
            TrendData.tag_id == tag_id
        ).order_by(TrendData.timestamp.desc()).first()
        
        if data:
            return (data.timestamp, data.value)
        return None


def get_latest_values_batch(tag_ids: List[int]) -> Dict[int, Tuple[datetime, float]]:
    """
    Получение последних значений для списка тегов одним запросом.
    Решает проблему N+1 запросов.
    
    Args:
        tag_ids: Список ID тегов
        
    Returns:
        Словарь {tag_id: (timestamp, value)}
    """
    if not tag_ids:
        return {}
    
    with get_session() as session:
        # Подзапрос для получения максимального timestamp для каждого тега
        from sqlalchemy import func
        
        subquery = session.query(
            TrendData.tag_id,
            func.max(TrendData.timestamp).label('max_ts')
        ).filter(
            TrendData.tag_id.in_(tag_ids)
        ).group_by(TrendData.tag_id).subquery()
        
        # Основной запрос с JOIN
        data = session.query(
            TrendData.tag_id,
            TrendData.timestamp,
            TrendData.value
        ).join(
            subquery,
            (TrendData.tag_id == subquery.c.tag_id) & 
            (TrendData.timestamp == subquery.c.max_ts)
        ).all()
        
        return {row.tag_id: (row.timestamp, row.value) for row in data}


def get_statistics(
    tag_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> dict:
    """
    Получение статистики по тегу за период.
    
    Returns:
        {min, max, avg, count}
    """
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=1)
    
    with get_session() as session:
        result = session.query(
            func.min(TrendData.value).label("min"),
            func.max(TrendData.value).label("max"),
            func.avg(TrendData.value).label("avg"),
            func.count(TrendData.id).label("count")
        ).filter(
            TrendData.tag_id == tag_id,
            TrendData.timestamp >= start_time,
            TrendData.timestamp <= end_time
        ).first()
        
        return {
            "min": result.min,
            "max": result.max,
            "avg": round(result.avg, 2) if result.avg else None,
            "count": result.count,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }


def get_all_tags() -> List[dict]:
    """Получение списка всех тегов с последними значениями"""
    with get_session() as session:
        tags = session.query(Tag).filter(Tag.is_active == True).all()
        
        result = []
        for tag in tags:
            latest = get_latest_value(tag.id)
            result.append({
                "id": tag.id,
                "name": tag.name,
                "description": tag.description,
                "db_number": tag.db_number,
                "address": tag.start_address,
                "data_type": tag.data_type,
                "latest_value": latest[1] if latest else None,
                "latest_time": latest[0].isoformat() if latest else None
            })
        
        return result


_CLEANUP_BATCH = 10_000  # строк за одну транзакцию


def cleanup_old_data(days: int = 30) -> int:
    """
    Удаление старых данных трендов батчами, чтобы не блокировать БД.
    После удаления запускает incremental_vacuum для возврата страниц.

    Returns:
        Количество удалённых записей
    """
    cutoff = datetime.now() - timedelta(days=days)
    total_deleted = 0

    while True:
        with get_session() as session:
            deleted = session.execute(
                text(
                    "DELETE FROM trend_data WHERE id IN "
                    "(SELECT id FROM trend_data WHERE timestamp < :cutoff LIMIT :batch)"
                ),
                {"cutoff": cutoff, "batch": _CLEANUP_BATCH},
            ).rowcount
        if not deleted:
            break
        total_deleted += deleted

    if total_deleted > 0:
        # Постепенно возвращаем освободившиеся страницы ОС (не VACUUM — не блокирует)
        with engine.connect() as conn:
            conn.execute(text("PRAGMA incremental_vacuum(2000)"))
            conn.commit()

    return total_deleted


