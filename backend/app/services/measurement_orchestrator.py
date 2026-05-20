# backend/app/services/measurement_orchestrator.py
"""Контроллер процесса измерения"""
import logging
from typing import List, Optional, Tuple
from app.services.file_storage_service import FileStorageService
from app.domain.exceptions import DomainException
from app.core.celery_app import celery_app
from app.tasks.cv_pipeline import process_measurement_task
from pathlib import Path

logger = logging.getLogger(__name__)

class MeasurementOrchestrator:
    def __init__(self, file_storage: FileStorageService, upload_dir: str):
        self._file_storage = file_storage
        self._upload_dir = Path(upload_dir)

    async def execute_measurement_workflow(
        self,
        files: List,
        marker_size_mm: float,
        user_id: int,
        product_id: Optional[int],
        manual_roi: Optional[str]
    ) -> dict:
        if len(files) != 3:
            raise DomainException("Exactly 3 files are required: front, side, top")

        self._upload_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []
        roi_tuple: Optional[Tuple[int, int, int, int]] = None
        
        if manual_roi:
            try:
                coords = [int(x.strip()) for x in manual_roi.split(",")]
                if len(coords) == 4:
                    roi_tuple = tuple(coords)
            except ValueError:
                logger.warning("Failed to parse manual ROI string")

        try:
            for file in files:
                path = await self._file_storage.save_upload_securely(file, self._upload_dir)
                saved_paths.append(path)

            task = process_measurement_task.delay(
                image_paths=saved_paths,
                marker_size_mm=marker_size_mm,
                user_id=user_id,
                product_id=product_id,
                manual_roi=roi_tuple,
            )

            logger.info("Measurement task started: task_id=%s, user_id=%d", task.id, user_id)
            return {"task_id": task.id, "status": "processing"}

        except DomainException:
            for path in saved_paths:
                self._file_storage.remove_file(path)
            raise
        except Exception as e:
            logger.error("Measurement workflow failed: %s", e, exc_info=True)
            for path in saved_paths:
                self._file_storage.remove_file(path)
            raise DomainException("Internal server error during measurement")