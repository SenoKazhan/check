# backend/app/api/v1/measurement.py
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query
from app.api.dependencies import get_current_user, require_permission
from app.db.models.user import User
from app.domain.permissions import Permission
from app.services.measurement_orchestrator import MeasurementOrchestrator
from app.services.file_storage_service import FileStorageService
from app.core.config import settings
from app.domain.exceptions import DomainException, ImageValidationException
from fastapi import HTTPException

router = APIRouter(prefix="/measurements", tags=["Measurements"])

def get_measurement_orchestrator() -> MeasurementOrchestrator:
    file_storage = FileStorageService(settings)
    return MeasurementOrchestrator(file_storage, settings.upload_dir)

@router.post("/start")
async def start_measurement(
    files: List[UploadFile] = File(..., min_items=3, max_items=3),
    marker_size_mm: float = Query(50.0),
    product_id: Optional[int] = Query(None),
    roi_front: Optional[str] = Query(None, description="ROI for front view: x1,y1,x2,y2"),
    roi_side: Optional[str] = Query(None, description="ROI for side view: x1,y1,x2,y2"),
    roi_top: Optional[str] = Query(None, description="ROI for top view: x1,y1,x2,y2"),
    current_user: User = Depends(require_permission(Permission.EXECUTE_MEASUREMENTS)),
    orchestrator: MeasurementOrchestrator = Depends(get_measurement_orchestrator)
):
    import json
    
    roi_dict = {}
    if roi_front:
        roi_dict["front"] = roi_front
    if roi_side:
        roi_dict["side"] = roi_side
    if roi_top:
        roi_dict["top"] = roi_top
    
    manual_roi_json = json.dumps(roi_dict) if roi_dict else None
    
    try:
        result = await orchestrator.execute_measurement_workflow(
            files=files,
            marker_size_mm=marker_size_mm,
            user_id=current_user.id,
            product_id=product_id,
            manual_roi=manual_roi_json
        )
        return result
    except ImageValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DomainException as e:
        raise HTTPException(status_code=400, detail=str(e))