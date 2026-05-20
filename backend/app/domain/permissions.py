# backend/app/domain/permissions.py
from enum import Enum, auto

class Permission(Enum):
    MANAGE_PRODUCTS = auto()
    MANAGE_USERS = auto()
    MANAGE_SETTINGS = auto()
    EXECUTE_MEASUREMENTS = auto()
    EXECUTE_PACKING = auto()

# Маппинг ролей на права (OCP: добавление новой роли не ломает старый код)
ROLE_PERMISSIONS = {
    "worker": [Permission.EXECUTE_MEASUREMENTS, Permission.EXECUTE_PACKING],
    "admin": [
        Permission.EXECUTE_MEASUREMENTS, Permission.EXECUTE_PACKING,
        Permission.MANAGE_PRODUCTS, Permission.MANAGE_USERS, Permission.MANAGE_SETTINGS
    ]
}