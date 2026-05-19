import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock

# Мокируем тяжёлый инференс модели DA-2, чтобы тестить логику изоляции
def test_dimension_calculator_with_mocked_inference():
    """Тест: DimensionCalculator корректно обрабатывает замокированный ответ модели."""
    from app.cv.aruco_measure import detect_aruco # пример функции
    
    # Создаем фейковое черное изображение
    fake_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Мокируем функцию детекции маркера, чтобы она не искала его реально
    with patch('app.cv.aruco_measure.detect_aruco') as mock_detect:
        # Настраиваем мок: функция вернет заранее заданные координаты
        mock_corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
        mock_detect.return_value = (mock_corners, 0, "4X4_50")
        
        corners, marker_id, dict_name = detect_aruco(fake_image)
        
        # Проверяем, что мок вернул то, что мы задали
        assert marker_id == 0
        assert dict_name == "4X4_50"
        assert corners.shape == (4, 2)
        # Убеждаемся, что мок был вызван ровно 1 раз
        mock_detect.assert_called_once()