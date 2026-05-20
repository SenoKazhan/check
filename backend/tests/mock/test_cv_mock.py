import numpy as np
from unittest.mock import patch
import app.cv.aruco_measure as aruco_module

def test_detect_aruco_mocked():
    """Тест: мокируем функцию детекции маркера на уровне модуля."""
    fake_image = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
    
    with patch('app.cv.aruco_measure.detect_aruco', return_value=(mock_corners, 42, "4X4_50")):
        corners, marker_id, dict_name = aruco_module.detect_aruco(fake_image)
        assert marker_id == 42
        assert dict_name == "4X4_50"
        assert corners.shape == (4, 2)