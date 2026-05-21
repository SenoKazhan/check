# backend/app/packing/solver.py
import math
from typing import List, Optional
from ortools.sat.python import cp_model

# Масштаб для перевода мм -> целые числа (точность 0.1 мм)
SCALE = 10

class BinPackingSolver:
    def __init__(self, time_limit_sec=30, n_variants=3, allow_rotation=True):
        self.time_limit = time_limit_sec
        self.n_variants = min(n_variants, 3)
        self.allow_rotation = allow_rotation

    def solve(self, items):
        expanded = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        if not expanded:
            return []

        ub_x = sum(max(it.length_mm, it.width_mm) for it in expanded) if self.allow_rotation else sum(it.length_mm for it in expanded)
        ub_y = sum(max(it.length_mm, it.width_mm) for it in expanded) if self.allow_rotation else sum(it.width_mm for it in expanded)
        ub_z = sum(it.height_mm for it in expanded)
        
        min_x = max(it.length_mm for it in expanded)
        min_y = max(it.width_mm for it in expanded)
        min_z = max(it.height_mm for it in expanded)

        ub_x, ub_y, ub_z = max(ub_x, min_x), max(ub_y, min_y), max(ub_z, min_z)

        # Вычисляем верхние границы в масштабе решателя
        target_l = int(math.ceil(ub_x * SCALE))
        target_w = int(math.ceil(ub_y * SCALE))
        target_h = int(math.ceil(ub_z * SCALE))

        # Стратегии оптимизации
        objectives = [
            # Вариант 1: Компактный (Минимизация объема коробки)
            # Линейная аппроксимация минимума X*Y*Z
            lambda x, y, z: x * target_w * target_h + y * target_l * target_h + z * target_l * target_w,
            
            # Вариант 2: Плоский (Минимизация высоты Z)
            lambda x, y, z: z * target_l * target_w + y * target_l + x,
            
            # Вариант 3: Высокий (Минимизация площади основания X*Y)
            lambda x, y, z: x * target_w + y * target_l + z
        ]

        results = []
        seen_volumes = set()
        time_per_variant = self.time_limit / max(1, self.n_variants)

        for i in range(self.n_variants):
            solution = self._solve_model(expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z, objectives[i], time_per_variant)
            if solution:
                vol_key = int(solution["volume"] * 100)
                if vol_key not in seen_volumes:
                    results.append(solution)
                    seen_volumes.add(vol_key)

        results.sort(key=lambda x: x['volume'])
        return results

    def _solve_model(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z, objective_func, time_limit):
        n = len(expanded)
        model = cp_model.CpModel()

        target_l = int(math.ceil(ub_x * SCALE))
        target_w = int(math.ceil(ub_y * SCALE))
        target_h = int(math.ceil(ub_z * SCALE))

        x = [model.NewIntVar(0, target_l, f"x{i}") for i in range(n)]
        y = [model.NewIntVar(0, target_w, f"y{i}") for i in range(n)]
        z = [model.NewIntVar(0, target_h, f"z{i}") for i in range(n)]

        rot = [model.NewBoolVar(f"rot{i}") for i in range(n)] if self.allow_rotation else [model.NewConstant(0) for _ in range(n)]

        dims = []
        for i, item in enumerate(expanded):
            l = int(math.ceil(item.length_mm * SCALE))
            w = int(math.ceil(item.width_mm * SCALE))
            h = int(math.ceil(item.height_mm * SCALE))

            l_eff = model.NewIntVar(min(l, w), max(l, w), f"l_eff{i}")
            w_eff = model.NewIntVar(min(l, w), max(l, w), f"w_eff{i}")
            h_eff = model.NewConstant(h)

            if self.allow_rotation:
                model.Add(l_eff == l).OnlyEnforceIf(rot[i].Not())
                model.Add(w_eff == w).OnlyEnforceIf(rot[i].Not())
                model.Add(l_eff == w).OnlyEnforceIf(rot[i])
                model.Add(w_eff == l).OnlyEnforceIf(rot[i])
            else:
                model.Add(l_eff == l)
                model.Add(w_eff == w)

            dims.append((l_eff, w_eff, h_eff))

        max_used_x = model.NewIntVar(int(min_x * SCALE), target_l, "max_used_x")
        max_used_y = model.NewIntVar(int(min_y * SCALE), target_w, "max_used_y")
        max_used_z = model.NewIntVar(int(min_z * SCALE), target_h, "max_used_z")
        
        for i in range(n):
            model.Add(x[i] + dims[i][0] <= max_used_x)
            model.Add(y[i] + dims[i][1] <= max_used_y)
            model.Add(z[i] + dims[i][2] <= max_used_z)

        # Ограничения непересечения
        for i in range(n):
            for j in range(i + 1, n):
                b = [model.NewBoolVar(f"b_{i}_{j}_{k}") for k in range(6)]
                model.Add(x[i] + dims[i][0] <= x[j]).OnlyEnforceIf(b[0])
                model.Add(x[j] + dims[j][0] <= x[i]).OnlyEnforceIf(b[1])
                model.Add(y[i] + dims[i][1] <= y[j]).OnlyEnforceIf(b[2])
                model.Add(y[j] + dims[j][1] <= y[i]).OnlyEnforceIf(b[3])
                model.Add(z[i] + dims[i][2] <= z[j]).OnlyEnforceIf(b[4])
                model.Add(z[j] + dims[j][2] <= z[i]).OnlyEnforceIf(b[5])
                model.AddBoolOr(b)

        # ГРАВИТАЦИЯ: сумма высот пола предметов
        # Вес снижен, чтобы гравитация работала как tie-breaker, а не ломала компактность
        z_sum = sum(z[i] for i in range(n))
        z_weight = SCALE 

        # ЦЕЛЕВАЯ ФУНКЦИЯ: Плотность коробки + Гравитация
        model.Minimize(
            objective_func(max_used_x, max_used_y, max_used_z) + 
            z_sum * z_weight 
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            placements = []
            real_l = solver.Value(max_used_x) / SCALE
            real_w = solver.Value(max_used_y) / SCALE
            real_h = solver.Value(max_used_z) / SCALE

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
                "box": (real_l, real_w, real_h),
                "volume": real_l * real_w * real_h / 1000,
                "placements": placements,
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible"
            }

        return None