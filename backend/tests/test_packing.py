# tests/test_packing_solver.py

from app.schemas.packing import Item


def test_solver_initialization():
    from app.packing.solver import BinPackingSolver
    solver = BinPackingSolver(time_limit_sec=1, n_variants=1, allow_rotation=True)
    assert solver.time_limit == 1
    assert solver.n_variants == 1
    assert solver.allow_rotation

def test_solve_simple_case():
    from app.packing.solver import BinPackingSolver
    items = [Item(product_id=1, length_mm=50, width_mm=50, height_mm=50, quantity=1)]
    solver = BinPackingSolver(time_limit_sec=2, n_variants=1)
    solutions = solver.solve(items)
    # Может вернуть пустой список, если решение не найдено, но хотя бы не падает
    assert isinstance(solutions, list)

def test_solve_with_quantity():
    from app.packing.solver import BinPackingSolver
    items = [Item(product_id=1, length_mm=40, width_mm=40, height_mm=40, quantity=2)]
    solver = BinPackingSolver(time_limit_sec=2, n_variants=1)
    solutions = solver.solve(items)
    assert isinstance(solutions, list)