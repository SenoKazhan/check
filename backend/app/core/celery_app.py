"""
Конфигурация Celery для асинхронной обработки задач.
"""

import os
from celery import Celery

# Создаем экземпляр приложения
celery_app = Celery(
    'worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['app.tasks.cv_pipeline']  # Явно указываем, где лежат задачи
)

# Настройки конфигурации
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=1,
    # Добавляем настройки для Windows
    worker_pool='solo',  # Важно для Windows!
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 минут
    task_soft_time_limit=25 * 60,  # 25 минут
)

print("✅ Celery app initialized")