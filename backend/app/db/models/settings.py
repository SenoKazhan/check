"""
Таблица динамических настроек системы.
Позволяет изменять параметры без перезапуска приложения.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..base import Base


class SystemSetting(Base):
    """Хранит пользовательские значения настроек, переопределяющие defaults из config."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Ключ настройки (должен совпадать с именем поля в Settings)
    key = Column(String(64), unique=True, nullable=False, index=True)
    
    # Тип значения для валидации при чтении
    value_type = Column(String(16), nullable=False)  # 'bool', 'int', 'float', 'str'
    
    # Значение хранится как строка, преобразование выполняется при чтении
    value_str = Column(Text, nullable=True)
    
    # Метаданные: кто изменил, когда
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Описание изменения (опционально)
    change_reason = Column(Text, nullable=True)

    # Связи
    updater = relationship("User", foreign_keys=[updated_by])

    def get_typed_value(self) -> bool | int | float | str | None:
        """Преобразует строковое значение в соответствующий тип."""
        if self.value_str is None:
            return None
        match self.value_type:
            case "bool":
                return self.value_str.lower() in ("true", "1", "yes")
            case "int":
                return int(self.value_str)
            case "float":
                return float(self.value_str)
            case "str":
                return self.value_str
            case _:
                return self.value_str