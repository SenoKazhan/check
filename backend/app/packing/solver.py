# backend/app/packing/solver.py
import math

from ortools.sat.python import cp_model

# Масштаб для перевода мм -> целые числа (точность 0.1 мм)
SCALE = 10


class BinPackingSolver:
    def __init__(self, time_limit_sec=30, n_variants=3, allow_rotation=True, enable_stability=True):
        self.time_limit = time_limit_sec
        self.n_variants = min(n_variants, 3)
        self.allow_rotation = allow_rotation
        self.enable_stability = enable_stability  # Включить constraint опоры

    def solve(self, items):
        expanded = []
        for item in items:
            for _ in range(item.quantity):
                expanded.append(item)

        if not expanded:
            return []

        ub_x = sum(max(it.length_mm, it.width_mm) for it in expanded) if self.allow_rotation else sum(
            it.length_mm for it in expanded)
        ub_y = sum(max(it.length_mm, it.width_mm)
                   for it in expanded) if self.allow_rotation else sum(it.width_mm for it in expanded)
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
            lambda x, y, z: x * target_w * target_h + y *
            target_l * target_h + z * target_l * target_w,

            # Вариант 2: Плоский (Минимизация высоты Z)
            lambda x, y, z: z * target_l * target_w + y * target_l + x,

            # Вариант 3: Высокий (Минимизация площади основания X*Y)
            lambda x, y, z: x * target_w + y * target_l + z
        ]

        results = []
        seen_volumes = set()
        time_per_variant = self.time_limit / max(1, self.n_variants)

        for i in range(self.n_variants):
            # Пробуем со stability, если включено
            solution = None
            if self.enable_stability:
                solution = self._solve_model(
                    expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                    objectives[i], time_per_variant, enable_support=True
                )
            # Fallback: без stability constraint
            if solution is None:
                solution = self._solve_model(
                    expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                    objectives[i], time_per_variant, enable_support=False
                )

            if solution:
                vol_key = int(solution["volume"] * 100)
                if vol_key not in seen_volumes:
                    results.append(solution)
                    seen_volumes.add(vol_key)

        results.sort(key=lambda x: x['volume'])
        return results

    def _solve_model(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z, objective_func, time_limit, enable_support=True):
        n = len(expanded)
        model = cp_model.CpModel()

        target_l = int(math.ceil(ub_x * SCALE))
        target_w = int(math.ceil(ub_y * SCALE))
        target_h = int(math.ceil(ub_z * SCALE))

        x = [model.NewIntVar(0, target_l, f"x{i}") for i in range(n)]
        y = [model.NewIntVar(0, target_w, f"y{i}") for i in range(n)]
        z = [model.NewIntVar(0, target_h, f"z{i}") for i in range(n)]

        rot = [model.NewBoolVar(f"rot{i}") for i in range(n)] if self.allow_rotation else [
            model.NewConstant(0) for _ in range(n)]

        dims = []
        for i, item in enumerate(expanded):
            length = int(math.ceil(item.length_mm * SCALE))
            width = int(math.ceil(item.width_mm * SCALE))
            height = int(math.ceil(item.height_mm * SCALE))

            l_eff = model.NewIntVar(
                min(length, width), max(length, width), f"l_eff{i}")
            w_eff = model.NewIntVar(
                min(length, width), max(length, width), f"w_eff{i}")
            h_eff = model.NewConstant(height)

            if self.allow_rotation:
                model.Add(l_eff == length).OnlyEnforceIf(rot[i].Not())
                model.Add(w_eff == width).OnlyEnforceIf(rot[i].Not())
                model.Add(l_eff == width).OnlyEnforceIf(rot[i])
                model.Add(w_eff == length).OnlyEnforceIf(rot[i])
            else:
                model.Add(l_eff == length)
                model.Add(w_eff == width)

            dims.append((l_eff, w_eff, h_eff))

        max_used_x = model.NewIntVar(
            int(min_x * SCALE), target_l, "max_used_x")
        max_used_y = model.NewIntVar(
            int(min_y * SCALE), target_w, "max_used_y")
        max_used_z = model.NewIntVar(
            int(min_z * SCALE), target_h, "max_used_z")

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

        # ============================================================
        # STABILITY CONSTRAINTS (Ограничения стабильности / опоры)
        # ============================================================
        # Каждый предмет должен иметь опору снизу:
        #   - либо стоять на полу коробки (z == 0)
        #   - либо стоять на верхней грани другого предмета (z[i] == z[j] + h[j])
        #
        # Также: предметы с большей площадью основания получают штраф
        # за размещение выше, чем предметы с меньшей площадью.
        # ============================================================

        if enable_support and n > 0:
            # --- 1. Constraint: каждый предмет имеет опору ---
            is_on_floor = [model.NewBoolVar(f"floor{i}") for i in range(n)]
            supported_by = {}

            for i in range(n):
                # is_on_floor[i] == 1  =>  z[i] == 0
                model.Add(z[i] == 0).OnlyEnforceIf(is_on_floor[i])

                for j in range(n):
                    if i == j:
                        continue
                    # supported_by[i][j] == 1  =>  z[i] == z[j] + height[j]
                    supported_by[(i, j)] = model.NewBoolVar(f"sup_{i}_{j}")
                    model.Add(z[i] == z[j] + dims[j][2]).OnlyEnforceIf(
                        supported_by[(i, j)]
                    )

                # Каждый предмет либо на полу, либо на каком-то другом
                supporters = [supported_by[(i, j)]
                              for j in range(n) if j != i]
                model.Add(is_on_floor[i] + sum(supporters) >= 1)

        # --- 2. Целевая функция с gravity + area-weighted penalty ---

        # Обычная гравитация: минимизировать сумму высот
        z_sum = sum(z[i] for i in range(n))
        z_weight = SCALE * 3  # Усилили гравитацию (было SCALE)

        # Area-weighted gravity penalty:
        # Предметы с БОЛЬШЕЙ площадью основания должны быть НИЖЕ.
        # Сначала создаем raw_areas для всех предметов (понадобятся и тут, и в penalty)
        raw_areas = []
        for i in range(n):
            raw_area = model.NewIntVar(0, target_l * target_w, f"ba{i}")
            model.AddMultiplicationEquality(raw_area, [dims[i][0], dims[i][1]])
            raw_areas.append(raw_area)

        area_weighted_z_terms = []
        for i in range(n):
            # Нормализованная площадь: scaled_area = raw_area // (SCALE * SCALE)
            # Приводит к ~см^2 (SCALE=10 → 1 единица = 1 см^2)
            scaled_area = model.NewIntVar(0, target_l * target_w, f"sa{i}")
            model.AddDivisionEquality(
                scaled_area, raw_areas[i], SCALE * SCALE)

            # area_z = z[i] * scaled_area
            area_z = model.NewIntVar(0, target_h * target_l * target_w, f"az{i}")
            model.AddMultiplicationEquality(area_z, [z[i], scaled_area])
            area_weighted_z_terms.append(area_z)

        area_weighted_z = sum(area_weighted_z_terms)
        # Усилили вес: раньше предметы с base=22500 и base=7500 получали
        # почти одинаковый z-penalty. Теперь разница заметнее.
        area_z_weight = SCALE * 5

        # --- Дополнительный penalty: "крупный на мелком" ---
        # Если предмет i стоит на предмете j, но площадь i > площадь j — штраф.
        # Это discourages ситуации, когда большой товар опирается на мелкий.
        # Два механизма:
        #   1. Hard constraint (опционально): area_i <= area_j * MAX_RATIO
        #   2. Soft penalty: большой штраф за каждое нарушение
        MAX_AREA_RATIO = 1.5  # Крупный может быть в ~1.5 раза больше основания
        big_on_small_penalty_terms = []
        if enable_support:
            # Soft penalty: достаточно большой, чтобы перевесить компактность
            PENALTY_PER_PAIR = max(1, target_l * target_w * SCALE)
            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    # (A) Hard constraint: supported_by => area_i <= area_j * MAX_RATIO
                    # raw_area[i] * 2 <= raw_area[j] * 3  эквивалентно  area_i <= area_j * 1.5
                    model.Add(
                        raw_areas[i] * 2 <= raw_areas[j] * 3
                    ).OnlyEnforceIf(supported_by[(i, j)])

                    # (B) Soft penalty: если area_i > area_j — дополнительный штраф
                    area_bigger = model.NewBoolVar(f"ab_{i}_{j}")
                    model.Add(raw_areas[i] > raw_areas[j]).OnlyEnforceIf(
                        area_bigger)
                    model.Add(raw_areas[i] <= raw_areas[j]).OnlyEnforceIf(
                        area_bigger.Not())

                    # both = supported_by[i][j] AND area_bigger
                    both = model.NewBoolVar(f"both_{i}_{j}")
                    model.AddBoolAnd([supported_by[(i, j)], area_bigger]).OnlyEnforceIf(
                        both)
                    model.AddBoolOr([supported_by[(i, j)].Not(), area_bigger.Not()]).OnlyEnforceIf(
                        both.Not())

                    big_on_small_penalty_terms.append(
                        both * PENALTY_PER_PAIR)

        big_on_small_penalty = sum(
            big_on_small_penalty_terms) if big_on_small_penalty_terms else 0

        # ЦЕЛЕВАЯ ФУНКЦИЯ: Основная метрика + Гравитация + Area-штраф + Big-on-small штраф
        model.Minimize(
            objective_func(max_used_x, max_used_y, max_used_z) +
            z_sum * z_weight +
            area_weighted_z * area_z_weight +
            big_on_small_penalty
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 8  # Параллельный поиск

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
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "stability_enabled": enable_support,
            }

        return None