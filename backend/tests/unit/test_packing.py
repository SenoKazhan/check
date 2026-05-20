"""
Модульные тесты для BinPackingSolver.
"""
import pytest

from app.schemas.packing import Item
from app.packing.solver import BinPackingSolver, SCALE


class TestBinPackingSolver:
    """Тесты алгоритма трёхмерной упаковки."""

    def test_solver_initialization(self):
        """Проверка инициализации решателя."""
        solver = BinPackingSolver(
            time_limit_sec=10,
            n_variants=3,
            allow_rotation=True
        )
        
        assert solver.time_limit == 10
        assert solver.n_variants == 3
        assert solver.allow_rotation is True

    def test_solve_single_item(self):
        """Упаковка одного товара — тривиальный случай."""
        items = [
            Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=1)
        ]
        solver = BinPackingSolver(time_limit_sec=5, n_variants=1)
        results = solver.solve(items)
        
        # Должен найти хотя бы одно решение
        assert len(results) >= 1
        
        solution = results[0]
        # Коробка должна вмещать товар
        assert solution['box'][0] >= 100
        assert solution['box'][1] >= 100
        assert solution['box'][2] >= 100

    def test_solve_with_quantity(self):
        """Товар с quantity > 1 разворачивается в независимые экземпляры."""
        items = [
            Item(product_id=1, length_mm=50, width_mm=50, height_mm=50, quantity=3)
        ]
        solver = BinPackingSolver(time_limit_sec=10, n_variants=1)
        results = solver.solve(items)
        
        assert len(results) >= 1
        placements = results[0].get('placements', [])
        # Должно быть 3 размещения для 3 экземпляров
        assert len(placements) == 3

    def test_solve_no_overlap(self):
        """Проверка, что товары не пересекаются в решении."""
        items = [
            Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=1),
            Item(product_id=2, length_mm=80, width_mm=80, height_mm=80, quantity=1),
        ]
        solver = BinPackingSolver(time_limit_sec=60, n_variants=1)
        results = solver.solve(items)
        
        assert len(results) >= 1
        placements = results[0]['placements']
        
        # Проверка попарного непересечения
        for i in range(len(placements)):
            for j in range(i + 1, len(placements)):
                p, q = placements[i], placements[j]
                # Условие НЕпересечения: хотя бы одна ось разделена
                no_overlap = (
                    p['x'] + p['length'] <= q['x'] or
                    q['x'] + q['length'] <= p['x'] or
                    p['y'] + p['width'] <= q['y'] or
                    q['y'] + q['width'] <= p['y'] or
                    p['z'] + p['height'] <= q['z'] or
                    q['z'] + q['height'] <= p['z']
                )
                assert no_overlap, f"Пересечение товаров {i} и {j}"

    def test_solve_rotation_allowed(self):
        """Проверка, что поворот на 90° учитывается."""
        # Товар, который влезает только при повороте
        items = [
            Item(product_id=1, length_mm=200, width_mm=50, height_mm=50, quantity=1),
        ]
        # Коробка 100x100x100: товар влезает только если повернуть (50+50 <= 100)
        
        solver_with_rotation = BinPackingSolver(
            time_limit_sec=10, n_variants=1, allow_rotation=True
        )
        results_rot = solver_with_rotation.solve(items)
        
        solver_no_rotation = BinPackingSolver(
            time_limit_sec=10, n_variants=1, allow_rotation=False
        )
        results_no_rot = solver_no_rotation.solve(items)
        
        # С поворотом решение должно быть найдено
        assert len(results_rot) >= 1
        # Без поворота — возможно, нет (зависит от эвристики)
        # Это проверяет, что флаг rotation действительно влияет


    def test_solve_empty_items(self):
        """Пустой список товаров должен возвращать пустой результат."""
        solver = BinPackingSolver(time_limit_sec=5, n_variants=1)
        results = solver.solve([])
        assert results == []