from app.core.celery_app import celery_app
from app.packing.solver import BinPackingSolver
from app.schemas.packing import Item

@celery_app.task(bind=True, max_retries=1)
def process_packing_task(self, items_data: list[dict], time_limit: int, n_variants: int):
    items = [Item(**d) for d in items_data]
    solver = BinPackingSolver(time_limit_sec=time_limit, n_variants=n_variants)
    return solver.solve(items)