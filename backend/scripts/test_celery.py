#!/usr/bin/env python3
"""Тест Celery: отправка задачи и получение результата."""
import sys
from pathlib import Path

# 1. Сначала добавляем корень проекта в пути поиска
# __file__ = .../backend/scripts/test_celery.py
# .parent = .../backend/scripts
# .parent.parent = .../backend (корень проекта)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 2. Теперь импортируем задачу (путь уже добавлен)
from app.workers.cv_tasks import process_images_task

if __name__ == "__main__":
    print("🚀 Отправка тестовой задачи в Celery...")
    
    # Используем фейковые пути для проверки работы очереди
    fake_paths = ["fake_front.jpg", "fake_side.jpg", "fake_top.jpg"]
    
    try:
        # Отправляем задачу
        result = process_images_task.delay(fake_paths)
        print(f"📤 Task ID: {result.id}")
        
        # Ждем результат (тайм-аут 10 секунд)
        print("⏳ Ожидание результата...")
        data = result.get(timeout=10)
        
        print(f"✅ Успех! Результат:")
        print(data)
        
    except Exception as e:
        print(f"❌ Ошибка выполнения задачи: {e}")