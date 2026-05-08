"""
3D Bin Packing Solver на основе CP-SAT (Google OR-Tools).
Алгоритм: Итеративное уменьшение размеров контейнера (Iterative Deepening).
"""

import math
from ortools.sat.python import cp_model

# Масштаб для перевода мм -> целые числа (точность 0.1 мм)
SCALE = 10


class BinPackingSolver:
    def __init__(self, time_limit_sec=15, n_variants=3, allow_rotation=True):
        self.time_limit = time_limit_sec
        self.n_variants = n_variants
        self.allow_rotation = allow_rotation

    def solve(self, items):
        """
        Главный метод. Находит n_variants вариантов упаковки минимального объема.
        """
        # Разворачиваем quantity (2 коробки = 2 независимых предмета)
        expanded = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        if not expanded:
            return []

        # 1. Оцениваем нижнюю границу (ниже этого размера точно не влезут)
        # Объем всех товаров
        total_vol = sum(p.length_mm * p.width_mm * p.height_mm for p in expanded)
        # Сторона куба с таким объемом
        approx_side = math.ceil((total_vol ** (1 / 3)) * 1.1)
        
        # Максимальный габарит самого большого товара
        max_l = max(p.length_mm for p in expanded)
        max_w = max(p.width_mm for p in expanded)
        max_h = max(p.height_mm for p in expanded)

        # Стартовый размер коробки (с запасом)
        current_l = max(max_l, approx_side) + 50
        current_w = max(max_w, approx_side) + 50
        current_h = max(max_h, approx_side) + 50

        results = []
        last_valid_volume = float('inf')

        # 2. Итеративный поиск: пробуем уменьшать коробку
        # Делаем до 50 итераций уменьшения
        for _ in range(50):
            # Проверяем, влезут ли товары в текущий размер
            # Время на одну проверку делим поровну на все варианты
            time_per_check = self.time_limit / self.n_variants
            
            solution = self._try_pack_fixed_box(
                expanded, current_l, current_w, current_h, time_per_check
            )

            if solution:
                volume = solution['volume']
                
                # Если это решение лучше предыдущего (меньше объем) и не дубликат
                if volume < last_valid_volume - 100: # -100 чтобы не дублировать похожие
                    results.append(solution)
                    last_valid_volume = volume
                    
                    # Если нашли достаточно вариантов, выходим
                    if len(results) >= self.n_variants:
                        break

                # Уменьшаем коробку для следующей попытки
                # Уменьшаем самую длинную сторону на 10мм (или 5%)
                sides = [(current_l, 'l'), (current_w, 'w'), (current_h, 'h')]
                sides.sort(reverse=True) # Сортируем по убыванию
                
                val, dim = sides[0]
                reduction = max(10, int(val * 0.05)) # Уменьшаем на 5% или минимум на 10мм
                
                if dim == 'l': current_l -= reduction
                elif dim == 'w': current_w -= reduction
                else: current_h -= reduction

            else:
                # Если в текущий размер не влезло, дальше уменьшать эту же конфигурацию нет смысла.
                # Но так как мы уменьшаем по одной оси, можно попробовать продолжить, 
                # однако обычно лучше остановить этот цикл.
                break

        # Сортируем результаты по объему
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

        dims = [] # Храним эффективные размеры для каждого предмета

        # Ограничения для каждого предмета
        for i, item in enumerate(expanded):
            l = int(math.ceil(item.length_mm * SCALE))
            w = int(math.ceil(item.width_mm * SCALE))
            h = int(math.ceil(item.height_mm * SCALE))

            # Эффективные размеры (могут меняться при повороте)
            l_eff = model.NewIntVar(min(l, w), max(l, w), f"l_eff{i}")
            w_eff = model.NewIntVar(min(l, w), max(l, w), f"w_eff{i}")
            h_eff = model.NewConstant(h) # Высоту не меняем

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

                model.Add(x[i] + l_i <= x[j]).OnlyEnforceIf(b[0]) # i слева от j
                model.Add(x[j] + l_j <= x[i]).OnlyEnforceIf(b[1]) # j слева от i
                model.Add(y[i] + w_i <= y[j]).OnlyEnforceIf(b[2]) # i сзади j
                model.Add(y[j] + w_j <= y[i]).OnlyEnforceIf(b[3]) # j сзади i
                model.Add(z[i] + h_i <= z[j]).OnlyEnforceIf(b[4]) # i ниже j
                model.Add(z[j] + h_j <= z[i]).OnlyEnforceIf(b[5]) # j ниже i

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
                "volume": box_l * box_w * box_h / 1000, # см^3
                "placements": placements,
                "status": "feasible"
            }
        
        return None