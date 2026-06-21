from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..base import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    value_type = Column(String(16), nullable=False)
    value_str = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    change_reason = Column(Text, nullable=True)

    updater = relationship("User", foreign_keys=[updated_by])

    def get_typed_value(self) -> bool | int | float | str | None:
        if self.value_str is None:
            return None
        match self.value_type:
            case "bool" | "boolean":
                return self.value_str.lower() in ("true", "1", "yes")
            case "int":
                return int(self.value_str)
            case "float" | "number":
                return float(self.value_str)
            case "str" | "string":
                return self.value_str
            case _:
                return self.value_str