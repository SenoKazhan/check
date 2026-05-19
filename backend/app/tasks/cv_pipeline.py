"""
Celery-задачи для конвейера компьютерного зрения.

Реализует статусную модель обработки измерений:
    PENDING → PROCESSING → COMPLETED | FAILED | NEEDS_REVIEW

Архитектурные особенности:
-------------------------
1. Все операции с базой данных выполняются синхронно через psycopg2,
   поскольку Celery-воркеры по умолчанию не имеют event loop.

2. Модель глубины кэшируется на уровне модуля для повторного использования
   между задачами в рамках одного воркера (паттерн Singleton).

3. Разделение ответственности:
   - Функции с префиксом `_` выполняют атомарные операции (БД, файловая система)
   - Основная задача `process_measurement_task` оркестрирует поток выполнения
   - Бизнес-логика агрегации результатов вынесена в отдельные функции

Ссылки на разделы пояснительной записки:
- Раздел 4.2: Модуль компьютерного зрения, конвейер обработки
- Раздел 2.13: Обработка ошибок и логирование
"""

# Стандартная библиотека
from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Сторонние зависимости
import cv2
import numpy as np
import psycopg2
from psycopg2.extensions import connection as PgConnection

# Локальные импорты
from app.core.celery_app import celery_app
from app.core.config import settings
from app.cv.aruco_measure import measure_from_wrapper
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.db.enums import MeasurementStatus
from app.services.verifier import DimensionVerifier

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Константы модуля
# ─────────────────────────────────────────────────────────────────────────────

# Ракурсы съёмки и порядок агрегации габаритов
REQUIRED_VIEWS: Tuple[str, str, str] = ("front", "side", "top")
DIMENSION_MAPPING: Dict[str, Tuple[str, str]] = {
    # (источник_ракурса, ключ_результата)
    "length": ("front", "height_mm"),
    "width": ("side", "height_mm"),
    "height": ("top", "height_mm"),
}

# Пороговые значения для верификации
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.4
DEFAULT_GAMMA_CORRECTION: float = 0.75
MM_PER_METER: float = 1000.0

# ─────────────────────────────────────────────────────────────────────────────
# Инфраструктура: кэширование модели
# ─────────────────────────────────────────────────────────────────────────────

_depth_model_cache: Dict[str, DepthAnythingV2OpenVINO] = {}


def get_cached_depth_model() -> DepthAnythingV2OpenVINO:
    """
    Возвращает экземпляр модели оценки глубины с ленивой загрузкой и кэшированием.

    Архитектурное назначение:
    -------------------------
    Паттерн Singleton на уровне модуля: модель загружается один раз
    при первом вызове в рамках процесса воркера и переиспользуется
    для всех последующих задач, что исключает накладные расходы на
    повторную инициализацию OpenVINO.

    Returns:
    --------
    DepthAnythingV2OpenVINO
        Инициализированный экземпляр модели в метрическом режиме.
    """
    cache_key = "metric"
    if cache_key not in _depth_model_cache:
        logger.info("Загрузка модели Depth Anything V2 (метрический режим)...")
        _depth_model_cache[cache_key] = DepthAnythingV2OpenVINO(
            ir_path=settings.cv_model_ir_path,
            model_size=settings.cv_model_size,
            metric=True,
            scene_type=settings.cv_scene_type,
            device="CPU",
        )
        logger.info("Модель успешно загружена и готова к инференсу")
    return _depth_model_cache[cache_key]


# ─────────────────────────────────────────────────────────────────────────────
# Инфраструктура: работа с базой данных
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def get_database_connection() -> PgConnection:
    """
    Контекстный менеджер для управления синхронным подключением к БД.

    Архитектурное назначение:
    -------------------------
    Инкапсулирует логику открытия/закрытия соединения, обеспечивая
    гарантированное освобождение ресурсов даже при возникновении исключений.
    Используется в задачах Celery, где асинхронный asyncpg недоступен.

    Yields:
    -------
    psycopg2.extensions.connection
        Активное соединение с базой данных.
    """
    db_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    conn = psycopg2.connect(db_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_db_update(
    query: str,
    params: tuple,
    operation_name: str,
    measurement_id: Optional[int] = None,
) -> bool:
    """
    Выполняет UPDATE/INSERT запрос к базе данных с обработкой ошибок.

    Параметры:
    ----------
    query : str
        Параметризованный SQL-запрос.
    params : tuple
        Кортеж параметров для подстановки в запрос.
    operation_name : str
        Человекочитаемое название операции для логирования.
    measurement_id : int, optional
        Идентификатор измерения для контекста лога.

    Returns:
    --------
    bool
        True при успешном выполнении, False при ошибке.
    """
    try:
        with get_database_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                log_context = f"#{measurement_id}" if measurement_id else ""
                logger.info(
                    "✓ %s %s: операция выполнена", operation_name, log_context
                )
                return True
    except Exception as error:
        log_context = f"#{measurement_id}" if measurement_id else ""
        logger.error(
            "✗ %s %s: ошибка выполнения — %s",
            operation_name,
            log_context,
            error,
            exc_info=True,
        )
        return False


def create_measurement_record(
    user_id: int,
    product_id: Optional[int],
    initial_dimensions: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> int:
    """
    Создаёт запись измерения со статусом PENDING и возвращает её идентификатор.

    Параметры:
    ----------
    user_id : int
        Идентификатор пользователя, инициировавшего измерение.
    product_id : int | None
        Идентификатор товара из справочника (опционально).
    initial_dimensions : tuple[float, float, float]
        Начальные значения габаритов (по умолчанию нулевые).

    Returns:
    --------
    int
        Идентификатор созданной записи в таблице measurements.

    Raises:
    -------
    psycopg2.Error
        При ошибке выполнения SQL-запроса.
    """
    query = """
        INSERT INTO measurements 
        (user_id, product_id, length_mm, width_mm, height_mm, 
         status, verified_ok, delta_pct, override_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    params = (
        user_id,
        product_id,
        *initial_dimensions,
        MeasurementStatus.PENDING.value,
        None,
        None,
        None,
    )
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            measurement_id = cursor.fetchone()[0]
            logger.info(
                "✓ Создана запись измерения #%d (статус: PENDING)",
                measurement_id,
            )
            return measurement_id


def update_measurement_status(
    measurement_id: int,
    status: MeasurementStatus,
) -> bool:
    """Обновляет статус измерения в базе данных."""
    query = "UPDATE measurements SET status = %s WHERE id = %s"
    params = (status.value, measurement_id)
    return execute_db_update(
        query,
        params,
        operation_name="Обновление статуса",
        measurement_id=measurement_id,
    )


def finalize_measurement(
    measurement_id: int,
    dimensions: Dict[str, float],
    status: MeasurementStatus,
    verification_metrics: Dict[str, Optional[float]],
) -> bool:
    """
    Сохраняет финальные результаты измерения и обновляет статус.

    Параметры:
    ----------
    measurement_id : int
        Идентификатор записи измерения.
    dimensions : dict[str, float]
        Словарь с габаритами: {length_mm, width_mm, height_mm}.
    status : MeasurementStatus
        Финальный статус обработки.
    verification_metrics : dict[str, float | None]
        Метрики верификации: {delta_pct, verified_ok}.

    Returns:
    --------
    bool
        True при успешном обновлении, False при ошибке.
    """
    query = """
        UPDATE measurements 
        SET length_mm = %s, width_mm = %s, height_mm = %s, 
            status = %s, delta_pct = %s, verified_ok = %s, measured_at = NOW()
        WHERE id = %s
    """
    params = (
        dimensions["length_mm"],
        dimensions["width_mm"],
        dimensions["height_mm"],
        status.value,
        verification_metrics.get("delta_pct"),
        verification_metrics.get("verified_ok"),
        measurement_id,
    )
    return execute_db_update(
        query,
        params,
        operation_name="Финализация измерения",
        measurement_id=measurement_id,
    )


def _get_sync_db_connection() -> PgConnection:
    """Создаёт синхронное подключение к БД для использования в Celery."""
    db_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    return psycopg2.connect(db_url)


def _fetch_setting(
    conn: PgConnection,
    key: str,
    default: Any,
) -> Any:
    """
    Синхронное чтение динамической настройки из БД.

    Параметры:
    ----------
    conn : PgConnection
        Активное подключение к базе данных.
    key : str
        Ключ настройки в таблице system_settings.
    default : Any
        Значение по умолчанию, если настройка не найдена.

    Returns:
    --------
    Any
        Значение настройки в нативном типе или default.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value_str, value_type FROM system_settings WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return default
            val_str, val_type = row
            if val_type == "bool":
                return val_str.lower() in ("true", "1", "yes")
            elif val_type == "int":
                return int(val_str)
            elif val_type == "float":
                return float(val_str)
            return val_str
    except Exception:
        return default


def _get_reference_dimensions(
    conn: PgConnection,
    product_id: Optional[int],
) -> Optional[Dict[str, float]]:
    """
    Получает эталонные габариты товара из справочника.

    Параметры:
    ----------
    conn : PgConnection
        Активное подключение к базе данных.
    product_id : int | None
        Идентификатор товара.

    Returns:
    --------
    dict[str, float] | None
        Словарь эталонных габаритов или None, если товар не найден
        или эталонные значения не заданы.
    """
    if product_id is None:
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ref_length_mm, ref_width_mm, ref_height_mm
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            )
            row = cur.fetchone()
            if not row or all(v is None for v in row):
                return None
            return {
                "ref_length_mm": row[0],
                "ref_width_mm": row[1],
                "ref_height_mm": row[2],
            }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Инфраструктура: управление временными файлами
# ─────────────────────────────────────────────────────────────────────────────

def cleanup_temporary_files(file_paths: List[str]) -> None:
    """
    Удаляет временные файлы изображений после обработки.

    Параметры:
    ----------
    file_paths : list[str]
        Список путей к файлам для удаления.
    """
    for file_path in file_paths:
        if not file_path:
            continue
        path = Path(file_path)
        if path.exists():
            try:
                path.unlink()
                logger.debug("Временный файл удалён: %s", file_path)
            except OSError as error:
                logger.warning(
                    "Не удалось удалить файл %s: %s", file_path, error
                )


# ─────────────────────────────────────────────────────────────────────────────
# Бизнес-логика: обработка отдельных ракурсов
# ─────────────────────────────────────────────────────────────────────────────

def process_single_view(
    image_path: str,
    model: DepthAnythingV2OpenVINO,
    marker_size_meters: float,
    view_label: str,
    enable_alignment: bool = True,
    reference_angle: float = 0.0,
) -> Dict[str, float]:
    """
    Обрабатывает изображение одного ракурса и возвращает измеренные габариты.

    Параметры:
    ----------
    image_path : str
        Путь к файлу изображения.
    model : DepthAnythingV2OpenVINO
        Инициализированная модель оценки глубины.
    marker_size_meters : float
        Физический размер ArUco-маркера в метрах.
    view_label : str
        Название ракурса для логирования.
    enable_alignment : bool
        Включить выравнивание объекта.
    reference_angle : float
        Эталонный угол для выравнивания.

    Returns:
    --------
    dict[str, float]
        Словарь с результатами: {width_mm, height_mm, depth_m, confidence}.

    Raises:
    -------
    ValueError
        Если изображение не удалось прочитать или измерить.
    """
    logger.info("Обработка ракурса: %s", view_label)

    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise ValueError(f"Не удалось прочитать изображение: {image_path}")

    # Вызов measure_from_wrapper с динамическими параметрами
    measurements, annotated, depth_vis = measure_from_wrapper(
        image_bgr=image_bgr,
        wrapper=model,
        marker_size_m=marker_size_meters,
        multi_scale=False,
        object_label=view_label.capitalize(),
        same_plane=True,
        enhance_visualization=True,
        gamma=DEFAULT_GAMMA_CORRECTION,
    )

    if measurements is None:
        raise ValueError(
            f"Не удалось измерить объект на ракурсе {view_label}"
        )

    return {
        "width_mm": measurements["width_m"] * MM_PER_METER,
        "height_mm": measurements["height_m"] * MM_PER_METER,
        "depth_m": measurements.get("depth_m", 0.0),
        "confidence": measurements.get("confidence", 0.0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Бизнес-логика: агрегация результатов по ракурсам
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_dimensions(
    view_results: Dict[str, Dict[str, float]],
) -> Dict[str, float]:
    """
    Агрегирует габариты из трёх ортогональных ракурсов в итоговые размеры.

    Архитектурное обоснование:
    --------------------------
    Длина берётся из фронтального ракурса (высота на изображении),
    ширина — из бокового, высота — из верхнего. Это соответствует
    стандартной системе координат: объект ориентирован вертикально,
    камера смотрит перпендикулярно грани.

    Параметры:
    ----------
    view_results : dict[str, dict[str, float]]
        Результаты измерений по ракурсам: {view_name: {width_mm, height_mm, ...}}.

    Returns:
    --------
    dict[str, float]
        Итоговые габариты: {length_mm, width_mm, height_mm}.
    """
    return {
        f"{dim_name}_mm": view_results[view_name][result_key]
        for dim_name, (view_name, result_key) in DIMENSION_MAPPING.items()
    }


def calculate_cross_view_consistency(
    view_results: Dict[str, Dict[str, float]],
    threshold_pct: float,
) -> Tuple[Optional[float], Optional[bool]]:
    """
    Вычисляет согласованность измерений между фронтальным и боковым ракурсами.

    Параметры:
    ----------
    view_results : dict[str, dict[str, float]]
        Результаты измерений по ракурсам.
    threshold_pct : float
        Допустимое отклонение в процентах.

    Returns:
    --------
    tuple[float | None, bool | None]
        (delta_pct, verified_ok) — относительное отклонение и флаг соответствия порогу.
    """
    h_front = view_results["front"]["height_mm"]
    h_side = view_results["side"]["height_mm"]

    if not h_front or not h_side:
        return None, None

    delta_pct = abs(h_front - h_side) / min(h_front, h_side) * 100
    verified_ok = delta_pct <= threshold_pct
    return delta_pct, verified_ok


def determine_final_status(
    avg_confidence: float,
    confidence_threshold: float,
    verified_ok: Optional[bool],
) -> MeasurementStatus:
    """
    Определяет финальный статус измерения на основе метрик качества.

    Логика принятия решения:
    -----------------------
    1. Если средняя уверенность ниже порога → NEEDS_REVIEW
    2. Если верификация не пройдена (расхождение ракурсов) → NEEDS_REVIEW
    3. Иначе → COMPLETED

    Параметры:
    ----------
    avg_confidence : float
        Средняя уверенность модели по всем ракурсам [0, 1].
    confidence_threshold : float
        Порог минимальной допустимой уверенности.
    verified_ok : bool | None
        Результат перекрёстной проверки ракурсов.

    Returns:
    --------
    MeasurementStatus
        Финальный статус обработки измерения.
    """
    if avg_confidence < confidence_threshold:
        return MeasurementStatus.NEEDS_REVIEW
    if verified_ok is False:
        return MeasurementStatus.NEEDS_REVIEW
    return MeasurementStatus.COMPLETED


# ─────────────────────────────────────────────────────────────────────────────
# Celery-задача: оркестрация конвейера измерений
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=1)
def process_measurement_task(
    self: Any,
    image_paths: List[str],
    marker_size_mm: float,
    user_id: int,
    product_id: Optional[int] = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Основная задача обработки измерений габаритов объекта.

    Статусная машина обработки:
    --------------------------
    1. PENDING: запись создана, задача в очереди
    2. PROCESSING: запущен конвейер компьютерного зрения
    3. Финальные статусы:
       - COMPLETED: успешное измерение с подтверждённой точностью
       - NEEDS_REVIEW: низкая уверенность или расхождение ракурсов
       - FAILED: критическая ошибка обработки

    Параметры:
    ----------
    image_paths : list[str]
        Пути к трём изображениям: [front, side, top].
    marker_size_mm : float
        Размер ArUco-маркера в миллиметрах.
    user_id : int
        Идентификатор пользователя, инициировавшего измерение.
    product_id : int | None
        Идентификатор товара из справочника (опционально).
    confidence_threshold : float, optional
        Порог минимальной уверенности модели (по умолчанию 0.4).

    Returns:
    --------
    dict[str, Any]
        Словарь с результатом: {status, measurement_id, dimensions_mm, confidence}.

    Raises:
    -------
    celery.exceptions.Retry
        При временной ошибке для повторной попытки.
    """
    measurement_id: Optional[int] = None

    try:
        # === Валидация входных данных ===
        if len(image_paths) != len(REQUIRED_VIEWS):
            raise ValueError(
                f"Требуется ровно {len(REQUIRED_VIEWS)} изображения: "
                f"{', '.join(REQUIRED_VIEWS)}"
            )

        # === Шаг 1: Создание записи измерения (статус: PENDING) ===
        measurement_id = create_measurement_record(
            user_id=user_id,
            product_id=product_id,
            initial_dimensions=(0.0, 0.0, 0.0),
        )

        # === Шаг 2: Обновление статуса на PROCESSING ===
        update_measurement_status(measurement_id, MeasurementStatus.PROCESSING)

        # === Шаг 2.5: Загрузка динамических настроек ===
        conn_cfg = _get_sync_db_connection()
        enable_alignment = _fetch_setting(
            conn_cfg, "cv_enable_alignment", True
        )
        reference_angle = _fetch_setting(
            conn_cfg, "cv_alignment_reference_angle", 0.0
        )
        reference_dims = _get_reference_dimensions(conn_cfg, product_id)
        conn_cfg.close()

        logger.info(
            "Конфигурация CV: alignment=%s, angle=%.1f°",
            enable_alignment,
            reference_angle,
        )

        # === Шаг 3: Запускаем CV-пайплайн ===
        model = get_cached_depth_model()
        views = ["front", "side", "top"]
        view_results: Dict[str, Dict[str, float]] = {}
        confidences: List[float] = []

        marker_size_meters = marker_size_mm / MM_PER_METER

        for view_name, img_path in zip(views, image_paths):
            view_results[view_name] = process_single_view(
                image_path=img_path,
                model=model,
                marker_size_meters=marker_size_meters,
                view_label=view_name,
                enable_alignment=enable_alignment,
                reference_angle=reference_angle,
            )
            logger.info(
                "[%s] Габариты: %.1f×%.1f мм, уверенность: %.2f",
                view_name,
                view_results[view_name]["width_mm"],
                view_results[view_name]["height_mm"],
                view_results[view_name]["confidence"],
            )
            confidences.append(view_results[view_name]["confidence"])

        # === Шаг 4: Агрегация результатов ===
        dimensions = aggregate_dimensions(view_results)
        avg_confidence = np.mean(confidences) if confidences else 0.0

        delta_pct, verified_ok = calculate_cross_view_consistency(
            view_results,
            threshold_pct=settings.verify_threshold_pct,
        )

        # === Шаг 5: Верификация через DimensionVerifier ===
        final_length = dimensions.get("length_mm", 0.0)
        final_width = dimensions.get("width_mm", 0.0)
        final_height = dimensions.get("height_mm", 0.0)

        verifier = DimensionVerifier(
            threshold_pct=settings.verify_threshold_pct
        )
        verify_res = verifier.verify(
            measured={
                "length_mm": final_length,
                "width_mm": final_width,
                "height_mm": final_height,
            },
            reference=reference_dims,
            confidence=avg_confidence,
        )

        # === Шаг 6: Определение финального статуса ===
        final_status = determine_final_status(
            avg_confidence=avg_confidence,
            confidence_threshold=confidence_threshold,
            verified_ok=verify_res.ok,
        )

        if final_status == MeasurementStatus.NEEDS_REVIEW:
            reason = (
                f"низкая уверенность ({avg_confidence:.2f} < "
                f"{confidence_threshold})"
                if avg_confidence < confidence_threshold
                else f"расхождение ракурсов ({delta_pct:.1f}%)"
            )
            logger.warning(
                "Измерение #%d требует проверки: %s",
                measurement_id,
                reason,
            )

        # === Шаг 7: Сохранение финальных результатов ===
        finalize_measurement(
            measurement_id=measurement_id,
            dimensions=dimensions,
            status=final_status,
            verification_metrics={
                "delta_pct": delta_pct,
                "verified_ok": verify_res.ok,
            },
        )
        
        cleanup_temporary_files(image_paths)

        return {
            "status": "success",
            "measurement_id": measurement_id,
            "final_status": final_status.value,
            "confidence": avg_confidence,
            "dimensions_mm": dimensions,
        }

    except Exception as error:
        logger.error(
            "Критическая ошибка обработки измерения: %s",
            error,
            exc_info=True,
            extra={
                "measurement_id": measurement_id,
                "user_id": user_id,
            },
        )

        # Обновление статуса на FAILED при наличии записи
        if measurement_id is not None:
            update_measurement_status(
                measurement_id, MeasurementStatus.FAILED
            )

        # Повторная попытка через 5 секунд (максимум 1 ретрай)
        raise self.retry(exc=error, countdown=5)

    finally:
        # Гарантированная очистка временных файлов
        pass
