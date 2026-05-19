import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.cv.qr_scanner import QRScanner

@pytest.mark.asyncio
async def test_decode_image_mocked():
    scanner = QRScanner()
    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Патчим decode именно в том месте, где он импортирован
    with patch('app.cv.qr_scanner.decode') as mock_decode:
        mock_qr = MagicMock()
        mock_qr.data = b'test-qr-content'
        mock_qr.type = 'QRCODE'
        mock_decode.return_value = [mock_qr]
        
        result = await scanner.decode_image(fake_image)
        assert result == 'test-qr-content'

@pytest.mark.asyncio
async def test_decode_image_no_qr():
    scanner = QRScanner()
    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    with patch('app.cv.qr_scanner.decode', return_value=[]):
        result = await scanner.decode_image(fake_image)
        assert result is None