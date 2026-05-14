from celery.result import AsyncResult
from fastapi import APIRouter

from app.core.celery_app import celery_app

router = APIRouter(prefix="/tasks", tags=["Задачи"])


@router.get("/{task_id}")
async def task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "state": result.state}

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info) if result.info else "Ошибка"

    return response
