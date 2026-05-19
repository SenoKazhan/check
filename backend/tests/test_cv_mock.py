# tests/test_cv_mock.py
import numpy as np
import pytest
from unittest.mock import patch

def test_detect_aruco_mocked():
    """Тест: мокируем функцию детекции маркера."""
    from app.cv.aruco_measure import detect_aruco

    fake_image = np.zeros((480, 640, 3), dtype=np.uint8)
    
    with patch('app.cv.aruco_measure.detect_aruco') as mock_detect:
        mock_corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
        mock_detect.return_value = (mock_corners, 42, "4X4_50")
        
        corners, marker_id, dict_name = detect_aruco(fake_image)
        
        assert marker_id == 42
        assert dict_name == "4X4_50"
        assert corners.shape == (4, 2)