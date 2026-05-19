import pytest
import numpy as np
from unittest.mock import patch, AsyncMock
from app.cv.qr_scanner import QRScanner

@pytest.mark.asyncio
async def test_decode_image_mocked():
    scanner = QRScanner()
    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    with patch('pyzbar.pyzbar.decode') as mock_decode:
        # Мок возвращает список с одним QRCodeData
        mock_qr = AsyncMock()
        mock_qr.data = b'test-qr-content'
        mock_qr.type = 'QRCODE'
        mock_decode.return_value = [mock_qr]
        
        result = await scanner.decode_image(fake_image)
        assert result == 'test-qr-content'

@pytest.mark.asyncio
async def test_decode_image_no_qr():
    scanner = QRScanner()
    fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    with patch('pyzbar.pyzbar.decode', return_value=[]):
        result = await scanner.decode_image(fake_image)
        assert result is None