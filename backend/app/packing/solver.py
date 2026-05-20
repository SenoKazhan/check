"""
3D Bin Packing Solver на основе CP-SAT (Google OR-Tools).
Алгоритм: Итеративное уменьшение размеров контейнера (Iterative Deepening) с возможностью подстановки стратегии поиска размеров.
"""

import math
from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
from ortools.sat.python import cp_model

# Масштаб для перевода мм -> целые числа (точность 0.1 мм)
SCALE = 10


class BoxSizeSearchStrategy(ABC):
    """Стратегия генерации последовательности размеров коробок для проверки."""
    @abstractmethod
    def generate_sizes(self, items: List) -> List[Tuple[float, float, float]]:
        """
        Генерирует список возможных размеров коробки (длина, ширина, высота) в мм.
        Порядок должен быть таким, чтобы первые элементы были заведомо большими (гарантия решения),
        а последующие - уменьшенными.
        """
        pass


class IterativeDeepeningStrategy(BoxSizeSearchStrategy):
    """
    Стратегия итеративного уменьшения коробки.
    Начальный размер вычисляется как сумма максимальных габаритов по всем осям (гарантирует вместимость),
    затем последовательно уменьшается самая длинная сторона на заданный процент.
    """

    def __init__(self, reduction_step: float = 0.05, min_reduction_mm: float = 10.0):
        self.reduction_step = reduction_step
        self.min_reduction_mm = min_reduction_mm

    def generate_sizes(self, items: List) -> List[Tuple[float, float, float]]:
        # Разворачиваем quantity для вычисления максимальных габаритов
        expanded = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        if not expanded:
            return []

        max_l = max(p.length_mm for p in expanded)
        max_w = max(p.width_mm for p in expanded)
        max_h = max(p.height_mm for p in expanded)

        # Гарантированный начальный размер: сумма трёх максимумов (заведомо больше любого возможного размещения)
        start_l = max_l + max_w + max_h
        start_w = max_l + max_w + max_h
        start_h = max_l + max_w + max_h

        sizes = [(start_l, start_w, start_h)]
        current_l, current_w, current_h = start_l, start_w, start_h

        # Генерируем уменьшенные размеры до тех пор, пока хотя бы одна сторона положительна
        for _ in range(100):  # ограничим количество итераций
            sides = [(current_l, 'l'), (current_w, 'w'), (current_h, 'h')]
            sides.sort(reverse=True)
            longest_dim, dim_name = sides[0]
            reduction = max(self.min_reduction_mm, longest_dim * self.reduction_step)
            if dim_name == 'l':
                current_l -= reduction
            elif dim_name == 'w':
                current_w -= reduction
            else:
                current_h -= reduction

            if current_l <= 0 or current_w <= 0 or current_h <= 0:
                break
            sizes.append((current_l, current_w, current_h))

        return sizes


class BinPackingSolver:
    def __init__(self, time_limit_sec=15, n_variants=3, allow_rotation=True,
                 size_strategy: Optional[BoxSizeSearchStrategy] = None):
        self.time_limit = time_limit_sec
        self.n_variants = n_variants
        self.allow_rotation = allow_rotation
        self.size_strategy = size_strategy or IterativeDeepeningStrategy()

    def solve(self, items):
        """
        Главный метод. Находит n_variants вариантов упаковки минимального объема.
        items: список объектов с полями length_mm, width_mm, height_mm, quantity, product_id.
        """
        # Разворачиваем quantity
        expanded = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        if not expanded:
            return []

        results = []
        # Получаем последовательность размеров коробок от стратегии
        candidate_sizes = self.size_strategy.generate_sizes(items)

        for box_l, box_w, box_h in candidate_sizes:
            # Распределяем время: на каждый кандидат даём равную долю от общего лимита
            time_per_check = self.time_limit / max(1, len(candidate_sizes))
            solution = self._try_pack_fixed_box(expanded, box_l, box_w, box_h, time_per_check)
            if solution:
                results.append(solution)
                if len(results) >= self.n_variants:
                    break

        # Сортируем по объёму
        results.sort(key=lambda x: x['volume'])
        return results

    def _try_pack_fixed_box(self, expanded, box_l, box_w, box_h, time_limit):
        """
        Пытается упаковать товары в строго заданную коробку box_l x box_w x box_h.
        Возвращает словарь решения или None.
        """
        n = len(expanded)
        model = cp_model.CpModel()

        # Переводим в инты (масштабирование)
        target_l = int(math.ceil(box_l * SCALE))
        target_w = int(math.ceil(box_w * SCALE))
        target_h = int(math.ceil(box_h * SCALE))
        max_dim = max(target_l, target_w, target_h) + 1000

        # Переменные координат
        x = [model.NewIntVar(0, max_dim, f"x{i}") for i in range(n)]
        y = [model.NewIntVar(0, max_dim, f"y{i}") for i in range(n)]
        z = [model.NewIntVar(0, max_dim, f"z{i}") for i in range(n)]

        # Переменные поворота (Bool)
        if self.allow_rotation:
            rot = [model.NewBoolVar(f"rot{i}") for i in range(n)]
        else:
            rot = [model.NewConstant(0) for _ in range(n)]

        dims = []  # Храним эффективные размеры для каждого предмета

        # Ограничения для каждого предмета
        for i, item in enumerate(expanded):
            l = int(math.ceil(item.length_mm * SCALE))
            w = int(math.ceil(item.width_mm * SCALE))
            h = int(math.ceil(item.height_mm * SCALE))

            # Эффективные размеры (могут меняться при повороте)
            l_eff = model.NewIntVar(min(l, w), max(l, w), f"l_eff{i}")
            w_eff = model.NewIntVar(min(l, w), max(l, w), f"w_eff{i}")
            h_eff = model.NewConstant(h)  # Высоту не меняем

            if self.allow_rotation:
                # Если rot[i] == 0 (False): l_eff = l, w_eff = w
                model.Add(l_eff == l).OnlyEnforceIf(rot[i].Not())
                model.Add(w_eff == w).OnlyEnforceIf(rot[i].Not())
                # Если rot[i] == 1 (True): l_eff = w, w_eff = l (поворот на 90 град)
                model.Add(l_eff == w).OnlyEnforceIf(rot[i])
                model.Add(w_eff == l).OnlyEnforceIf(rot[i])
            else:
                model.Add(l_eff == l)
                model.Add(w_eff == w)

            # Границы контейнера
            model.Add(x[i] + l_eff <= target_l)
            model.Add(y[i] + w_eff <= target_w)
            model.Add(z[i] + h_eff <= target_h)

            dims.append((l_eff, w_eff, h_eff))

        # Ограничения НЕПЕРЕСЕЧЕНИЯ (для каждой пары)
        for i in range(n):
            for j in range(i + 1, n):
                l_i, w_i, h_i = dims[i]
                l_j, w_j, h_j = dims[j]

                # 6 условий непересечения (хотя бы одно должно быть истинным)
                b = [model.NewBoolVar(f"b_{i}_{j}_{k}") for k in range(6)]

                model.Add(x[i] + l_i <= x[j]).OnlyEnforceIf(b[0])  # i слева от j
                model.Add(x[j] + l_j <= x[i]).OnlyEnforceIf(b[1])  # j слева от i
                model.Add(y[i] + w_i <= y[j]).OnlyEnforceIf(b[2])  # i сзади j
                model.Add(y[j] + w_j <= y[i]).OnlyEnforceIf(b[3])  # j сзади i
                model.Add(z[i] + h_i <= z[j]).OnlyEnforceIf(b[4])  # i ниже j
                model.Add(z[j] + h_j <= z[i]).OnlyEnforceIf(b[5])  # j ниже i

                model.AddBoolOr(b)

        # Запуск решателя
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            placements = []
            for i, item in enumerate(expanded):
                l_val = solver.Value(dims[i][0]) / SCALE
                w_val = solver.Value(dims[i][1]) / SCALE
                h_val = solver.Value(dims[i][2]) / SCALE

                placements.append({
                    "product_id": item.product_id,
                    "x": solver.Value(x[i]) / SCALE,
                    "y": solver.Value(y[i]) / SCALE,
                    "z": solver.Value(z[i]) / SCALE,
                    "length": l_val,
                    "width": w_val,
                    "height": h_val,
                    "rotation": solver.Value(rot[i]) == 1 if self.allow_rotation else False,
                })

            return {
                "box": (box_l, box_w, box_h),
                "volume": box_l * box_w * box_h / 1000,  # см^3
                "placements": placements,
                "status": "feasible"
            }

        return None