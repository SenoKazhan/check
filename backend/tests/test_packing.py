# tests/test_packing.py
from app.packing.solver import BinPackingSolver
from app.schemas.packing import Item

def test_bin_packing_solver_finds_solution():
    """Тест: решатель находит хотя бы один вариант упаковки для простого набора."""
    items = [
        Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=2)
    ]
    
    # Проверьте, как инициализируется BinPackingSolver
    # Возможно, нужно передать размеры контейнера
    solver = BinPackingSolver(
        container_length_mm=600,   # 👈 Добавьте размеры контейнера
        container_width_mm=400,    # 👈 если они обязательны
        container_height_mm=400,   # 👈
        time_limit_sec=5, 
        n_variants=1
    )
    
    solutions = solver.solve(items)
    
    # Решение должно быть найдено
    assert len(solutions) > 0, "Solver should find at least one solution"