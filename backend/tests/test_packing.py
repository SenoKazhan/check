import pytest
from app.packing.solver import BinPackingSolver
from app.schemas.packing import Item

def test_bin_packing_solver_finds_solution():
    """Тест: решатель находит хотя бы один вариант упаковки для простого набора."""
    items = [
        Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=2)
    ]
    
    solver = BinPackingSolver(time_limit_sec=5, n_variants=1)
    solutions = solver.solve(items)
    
    # Решение должно быть найдено
    assert len(solutions) > 0
    # Коробка должна вмещать товар
    assert solutions[0]["box"][0] >= 100