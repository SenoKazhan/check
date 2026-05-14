"""
Перечисления (enums) для базы данных.
Соответствуют ограничениям CHECK в схеме БД.
"""
import enum


class MeasurementStatus(str, enum.Enum):
    """Статусы измерения габаритов."""
    PENDING = "pending"    # Задача в очереди / обрабатывается
    DONE = "done"          # Успешно завершено
    ERROR = "error"        # Ошибка при обработке


class SessionStatus(str, enum.Enum):
    """Статусы сеанса упаковки."""
    PENDING = "pending"
    DONE = "done"
    ERROR = "error"


class UserRole(str, enum.Enum):
    """Роли пользователей."""
    WORKER = "worker"
    ADMIN = "admin"