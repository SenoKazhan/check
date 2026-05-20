# backend/app/services/file_storage_service.py
import os
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import ApplicationSettings
from app.domain.exceptions import ImageValidationException
import cv2
import numpy as np

class FileStorageService:
    def __init__(self, settings: ApplicationSettings):
        self._settings = settings

    def validate_image(self, content: bytes) -> tuple[int, int]:
        try:
            img_array = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("Decoding failed")
            h, w = img.shape[:2]
            if w < self._settings.min_image_width or h < self._settings.min_image_height:
                raise ValueError(f"Resolution {w}x{h} is below minimum")
            return w, h
        except Exception as e:
            raise ImageValidationException(f"Image validation failed: {str(e)}")

    async def save_upload_securely(self, file: UploadFile, upload_dir: Path) -> str:
        if file.content_type not in self._settings.allowed_image_types:
            raise ImageValidationException(f"Invalid content type: {file.content_type}")
        
        content = await file.read()
        if len(content) > self._settings.max_upload_size_mb * 1024 * 1024:
            raise ImageValidationException("File size exceeds limit")
        
        self.validate_image(content)

        file_extension = Path(file.filename).suffix.lower() or ".jpg"
        if file_extension not in [".jpg", ".jpeg", ".png"]:
            file_extension = ".jpg"
        
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = upload_dir / unique_filename

        with open(file_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        return str(file_path)

    def remove_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)