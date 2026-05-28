"""
Сервис для работы с данными трендов.
Функции для запроса и анализа исторических данных.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
from sqlalchemy import func, text
from pathlib import Path
import logging

from app.storage import get_session, Tag, TrendData
from app.storage.database import engine, get_monthly_session, get_monthly_db_url, IS_TESTING

logger = logging.getLogger('trends')


def get_months_in_range(start: datetime, end: datetime) -> List[datetime]:
    """Получить список начальных дат месяцев в интервале"""
    months = []
    current = datetime(start.year, start.month, 1)
    target = datetime(end.year, end.month, 1)
    while current <= target:
        months.append(current)
        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)
    return months


def downsample_minmax(
    data: List[Tuple[datetime, float]], 
    target_points: int = 1500
) -> List[Tuple[datetime, float]]:
    """
    Алгоритм MinMax downsampling для уменьшения количества точек на графике
    с сохранением экстремумов (пиков и спадов).
    Разбивает данные на target_points // 2 корзин, выбирая min и max в каждой.
    """
    if len(data) <= target_points:
        return data

    # По 2 точки на корзину (минимум и максимум)
    num_buckets = max(1, target_points // 2)
    bucket_size = len(data) / num_buckets

    downsampled = []
    for i in range(num_buckets):
        start_idx = int(i * bucket_size)
        end_idx = int((i + 1) * bucket_size)
        bucket = data[start_idx:end_idx]
        if not bucket:
            continue

        min_point = min(bucket, key=lambda x: x[1])
        max_point = max(bucket, key=lambda x: x[1])

        # Добавляем в хронологическом порядке
        if min_point[0] < max_point[0]:
            downsampled.append(min_point)
            downsampled.append(max_point)
        elif min_point[0] > max_point[0]:
            downsampled.append(max_point)
            downsampled.append(min_point)
        else:
            downsampled.append(min_point)

    return downsampled


def get_trend_data(
    tag_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 200000,
    downsample_to: Optional[int] = None
) -> List[Tuple[datetime, float]]:
    """
    Получение данных тренда за период из ежемесячных БД.
    
    Args:
        tag_id: ID тега
        start_time: Начало периода (по умолчанию - последний час)
        end_time: Конец периода (по умолчанию - сейчас)
        limit: Максимум записей для извлечения из каждой БД
        downsample_to: До скольких точек downsample-ить результат (None - без downsampling)
    
    Returns:
        Список кортежей (timestamp, value)
    """
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=1)
    
    if IS_TESTING:
        with get_session() as session:
            data = session.query(TrendData.timestamp, TrendData.value).filter(
                TrendData.tag_id == tag_id,
                TrendData.timestamp >= start_time,
                TrendData.timestamp <= end_time
            ).order_by(TrendData.timestamp).limit(limit).all()
            results = [(row.timestamp, row.value) for row in data]
            if downsample_to:
                results = downsample_minmax(results, downsample_to)
            return results
            
    months = get_months_in_range(start_time, end_time)
    results = []
    
    for dt in months:
        # Проверяем, существует ли файл БД, чтобы зря не создавать пустые файлы при исторических запросах
        from app.config.settings import DATABASE_URL
        monthly_url = get_monthly_db_url(DATABASE_URL, dt)
        if monthly_url.startswith("sqlite:///"):
            path_str = monthly_url[len("sqlite:///")]
            if not Path(path_str).exists():
                if dt.year != datetime.now().year or dt.month != datetime.now().month:
                    continue
                    
        with get_monthly_session(dt) as session:
            data = session.query(TrendData.timestamp, TrendData.value).filter(
                TrendData.tag_id == tag_id,
                TrendData.timestamp >= start_time,
                TrendData.timestamp <= end_time
            ).order_by(TrendData.timestamp).limit(limit).all()
            results.extend([(row.timestamp, row.value) for row in data])
            
    results.sort(key=lambda x: x[0])
    
    # Если точек больше лимита, берём последние
    if len(results) > limit:
        results = results[-limit:]
        
    if downsample_to:
        results = downsample_minmax(results, downsample_to)
    elif len(results) > 100000:
        # Автоматический предохранитель для огромных интервалов (например, несколько недель)
        # downsample-им до 50 000 точек, что сохраняет высочайшую детализацию.
        results = downsample_minmax(results, 50000)
        
    return results


def get_latest_value(tag_id: int) -> Optional[Tuple[datetime, float]]:
    """Получение последнего значения тега из ежемесячных БД"""
    if IS_TESTING:
        with get_session() as session:
            data = session.query(TrendData.timestamp, TrendData.value).filter(
                TrendData.tag_id == tag_id
            ).order_by(TrendData.timestamp.desc()).first()
            if data:
                return (data.timestamp, data.value)
            return None

    current_dt = datetime.now()
    # Ищем за последние 12 месяцев
    for i in range(12):
        dt = current_dt - timedelta(days=30 * i)
        month_dt = datetime(dt.year, dt.month, 1)
        
        from app.config.settings import DATABASE_URL
        monthly_url = get_monthly_db_url(DATABASE_URL, month_dt)
        if monthly_url.startswith("sqlite:///"):
            path_str = monthly_url[len("sqlite:///")]
            if not Path(path_str).exists():
                if i > 0:  # Текущий месяц всегда опрашиваем
                    continue
                    
        with get_monthly_session(month_dt) as session:
            data = session.query(TrendData.timestamp, TrendData.value).filter(
                TrendData.tag_id == tag_id
            ).order_by(TrendData.timestamp.desc()).first()
            if data:
                return (data.timestamp, data.value)
    return None


def get_latest_values_batch(tag_ids: List[int]) -> Dict[int, Tuple[datetime, float]]:
    """
    Получение последних значений для списка тегов одним запросом.
    Сканирует ежемесячные БД в обратном направлении.
    """
    if not tag_ids:
        return {}
        
    if IS_TESTING:
        with get_session() as session:
            subquery = session.query(
                TrendData.tag_id,
                func.max(TrendData.timestamp).label('max_ts')
            ).filter(
                TrendData.tag_id.in_(tag_ids)
            ).group_by(TrendData.tag_id).subquery()
            
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

    result_dict = {}
    remaining_ids = set(tag_ids)
    current_dt = datetime.now()
    
    for i in range(12):
        if not remaining_ids:
            break
            
        dt = current_dt - timedelta(days=30 * i)
        month_dt = datetime(dt.year, dt.month, 1)
        
        from app.config.settings import DATABASE_URL
        monthly_url = get_monthly_db_url(DATABASE_URL, month_dt)
        if monthly_url.startswith("sqlite:///"):
            path_str = monthly_url[len("sqlite:///")]
            if not Path(path_str).exists():
                if i > 0:
                    continue
                    
        with get_monthly_session(month_dt) as session:
            subquery = session.query(
                TrendData.tag_id,
                func.max(TrendData.timestamp).label('max_ts')
            ).filter(
                TrendData.tag_id.in_(list(remaining_ids))
            ).group_by(TrendData.tag_id).subquery()
            
            data = session.query(
                TrendData.tag_id,
                TrendData.timestamp,
                TrendData.value
            ).join(
                subquery,
                (TrendData.tag_id == subquery.c.tag_id) & 
                (TrendData.timestamp == subquery.c.max_ts)
            ).all()
            
            for row in data:
                result_dict[row.tag_id] = (row.timestamp, row.value)
                remaining_ids.discard(row.tag_id)
                
    return result_dict


def get_statistics(
    tag_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None
) -> dict:
    """
    Получение статистики по тегу за период, объединяя данные из нужных ежемесячных БД.
    """
    if end_time is None:
        end_time = datetime.now()
    if start_time is None:
        start_time = end_time - timedelta(hours=1)
        
    if IS_TESTING:
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

    months = get_months_in_range(start_time, end_time)
    mins = []
    maxs = []
    sums = 0.0
    total_count = 0
    
    for dt in months:
        from app.config.settings import DATABASE_URL
        monthly_url = get_monthly_db_url(DATABASE_URL, dt)
        if monthly_url.startswith("sqlite:///"):
            path_str = monthly_url[len("sqlite:///")]
            if not Path(path_str).exists():
                if dt.year != datetime.now().year or dt.month != datetime.now().month:
                    continue
                    
        with get_monthly_session(dt) as session:
            result = session.query(
                func.min(TrendData.value).label("min"),
                func.max(TrendData.value).label("max"),
                func.sum(TrendData.value).label("sum"),
                func.count(TrendData.id).label("count")
            ).filter(
                TrendData.tag_id == tag_id,
                TrendData.timestamp >= start_time,
                TrendData.timestamp <= end_time
            ).first()
            
            if result and result.count > 0:
                if result.min is not None:
                    mins.append(result.min)
                if result.max is not None:
                    maxs.append(result.max)
                if result.sum is not None:
                    sums += result.sum
                total_count += result.count
                
    return {
        "min": min(mins) if mins else None,
        "max": max(maxs) if maxs else None,
        "avg": round(sums / total_count, 2) if total_count > 0 else None,
        "count": total_count,
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


def delete_trend_data_for_tag(tag_id: int) -> int:
    """Удаление данных тренда для тега из всех ежемесячных баз данных"""
    from app.config.settings import DATABASE_URL
    
    if IS_TESTING or not DATABASE_URL.startswith("sqlite:///"):
        with get_session() as session:
            return session.query(TrendData).filter(TrendData.tag_id == tag_id).delete()
            
    path_str = DATABASE_URL[len("sqlite:///")]
    db_path = Path(path_str)
    db_dir = db_path.parent
    base_name = db_path.stem
    
    total_deleted = 0
    pattern = f"{base_name}_data_*.db"
    for file in db_dir.glob(pattern):
        try:
            parts = file.stem.split('_data_')
            if len(parts) == 2:
                year, month = map(int, parts[1].split('_'))
                dt = datetime(year, month, 1)
                with get_monthly_session(dt) as session:
                    deleted = session.query(TrendData).filter(TrendData.tag_id == tag_id).delete()
                    total_deleted += deleted
        except Exception as e:
            logger.error(f"Failed to delete trend data from {file.name}: {e}")
            
    return total_deleted


def get_total_trend_count() -> int:
    """Получить общее количество записей трендов во всех базах данных"""
    from app.config.settings import DATABASE_URL
    
    if IS_TESTING or not DATABASE_URL.startswith("sqlite:///"):
        with get_session() as session:
            return session.query(TrendData).count()
            
    path_str = DATABASE_URL[len("sqlite:///")]
    db_path = Path(path_str)
    db_dir = db_path.parent
    base_name = db_path.stem
    
    total = 0
    pattern = f"{base_name}_data_*.db"
    for file in db_dir.glob(pattern):
        try:
            parts = file.stem.split('_data_')
            if len(parts) == 2:
                year, month = map(int, parts[1].split('_'))
                dt = datetime(year, month, 1)
                with get_monthly_session(dt) as session:
                    total += session.query(TrendData).count()
        except Exception as e:
            logger.error(f"Failed to count trends in {file.name}: {e}")
            
    return total


def get_global_latest_record() -> Optional[Tuple[datetime, float]]:
    """Получить последнюю запись тренда среди всех баз данных"""
    if IS_TESTING:
        with get_session() as session:
            last = session.query(TrendData.timestamp, TrendData.value).order_by(TrendData.timestamp.desc()).first()
            if last:
                return (last.timestamp, last.value)
            return None

    current_dt = datetime.now()
    for i in range(12):
        dt = current_dt - timedelta(days=30 * i)
        month_dt = datetime(dt.year, dt.month, 1)
        
        from app.config.settings import DATABASE_URL
        monthly_url = get_monthly_db_url(DATABASE_URL, month_dt)
        if monthly_url.startswith("sqlite:///"):
            path_str = monthly_url[len("sqlite:///")]
            if not Path(path_str).exists():
                if i > 0:
                    continue
                    
        with get_monthly_session(month_dt) as session:
            last = session.query(TrendData.timestamp, TrendData.value).order_by(TrendData.timestamp.desc()).first()
            if last:
                return (last.timestamp, last.value)
    return None


_CLEANUP_BATCH = 10_000  # строк за одну транзакцию


def cleanup_old_data(days: int = 30) -> int:
    """
    Удаление старых данных трендов батчами (устаревший метод для совместимости).
    """
    if IS_TESTING:
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
        return total_deleted
    return 0



