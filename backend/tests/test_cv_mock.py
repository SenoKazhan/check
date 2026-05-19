# tests/test_cv_mock.py
import numpy as np
from unittest.mock import patch
from app.cv.aruco_measure import detect_aruco

def test_dimension_calculator_with_mocked_inference():
    """Тест: корректно обрабатывает замокированный ответ модели."""
    fake_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    with patch('app.cv.aruco_measure.detect_aruco') as mock_detect:
        # Настраиваем мок на возврат КОРРЕКТНЫХ данных (corners, marker_id, dict_name)
        mock_corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
        mock_detect.return_value = (mock_corners, 0, "4X4_50")  # 👈 Все три значения
        
        corners, marker_id, dict_name = detect_aruco(fake_image)
        
        # Проверки
        assert marker_id == 0
        assert dict_name == "4X4_50"
        assert corners is not None
        assert corners.shape == (4, 2)