"""
Перечисления (enums) для базы данных.
Соответствуют ограничениям CHECK в схеме БД.
"""
import enum

class MeasurementStatus(str, enum.Enum):
    """Статусы обработки измерения."""
    PENDING = "pending"           # Запись создана, задача в очереди
    PROCESSING = "processing"     # Идёт обработка в Celery
    COMPLETED = "completed"       # Успешное завершение
    FAILED = "failed"             # Ошибка обработки
    NEEDS_REVIEW = "needs_review" # Требует проверки


class SessionStatus(str, enum.Enum):
    """Статусы сеанса упаковки."""
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


class UserRole(str, enum.Enum):
    """Роли пользователей."""
    WORKER = "worker"
    ADMIN = "admin"