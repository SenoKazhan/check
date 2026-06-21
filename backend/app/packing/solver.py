import math
from ortools.sat.python import cp_model

SCALE = 10


class BinPackingSolver:
    MAX_VARIANTS = 10
    SHAPE_STRATEGIES = ("compact", "flat", "tower", "long_x", "long_y", "cube")
    MIN_TIME_PER_VARIANT = 3.0

    def __init__(self, time_limit_sec=30, n_variants=3, allow_rotation=True, enable_stability=True):
        self.time_limit = time_limit_sec
        self.n_variants = max(1, min(int(n_variants), self.MAX_VARIANTS))
        self.allow_rotation = allow_rotation
        self.enable_stability = enable_stability

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

        time_per_variant = max(
            self.MIN_TIME_PER_VARIANT,
            self.time_limit / max(1, self.n_variants)
        )

        results = []
        for i in range(self.n_variants):
            strategy = self.SHAPE_STRATEGIES[i % len(self.SHAPE_STRATEGIES)]
            seed = i

            solution = None
            if self.enable_stability:
                solution = self._solve_variant(
                    expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                    strategy, time_per_variant, enable_support=True, seed=seed
                )
            if solution is None:
                solution = self._solve_variant(
                    expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                    strategy, time_per_variant, enable_support=False, seed=seed
                )

            if solution:
                solution["strategy"] = strategy
                results.append(solution)

        results.sort(key=lambda r: r["volume"])
        return results

    def _solve_variant(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                        strategy, time_limit, enable_support, seed):
        n = len(expanded)

        phase1_share = 0.0 if strategy == "compact" else 0.3
        phase1_time = max(2.0, time_limit * phase1_share)
        phase2_time = max(2.0, time_limit - phase1_time)

        shape_bound = None
        if strategy != "compact":
            shape_bound = self._solve_phase1(
                expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                strategy, phase1_time, enable_support, seed
            )

        return self._solve_phase2(
            expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
            strategy, shape_bound, phase2_time if shape_bound is not None else time_limit,
            enable_support, seed
        )

    def _solve_phase1(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                       strategy, time_limit, enable_support, seed):
        ctx = self._build_model(expanded, ub_x, ub_y, ub_z, min_x,
                                 min_y, min_z, enable_support=False)
        model = ctx["model"]
        metric_expr, metric_ub = self._shape_metric(ctx, strategy)
        if metric_expr is None:
            return None

        model.Minimize(metric_expr)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = seed
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return solver.Value(metric_expr)
        return None

    def _solve_phase2(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z,
                       strategy, shape_bound, time_limit, enable_support, seed):
        ctx = self._build_model(expanded, ub_x, ub_y, ub_z, min_x,
                                 min_y, min_z, enable_support=enable_support)
        model = ctx["model"]
        n = ctx["n"]
        max_used_x, max_used_y, max_used_z = ctx["max_used"]

        if shape_bound is not None:
            metric_expr, metric_ub = self._shape_metric(ctx, strategy)
            if metric_expr is not None:
                tolerance = max(1, int(math.ceil(shape_bound * 0.03)))
                model.Add(metric_expr <= shape_bound + tolerance)

        vol_ub = ctx["target_l"] * ctx["target_w"] * ctx["target_h"]
        vol_var = model.NewIntVar(0, vol_ub, "box_volume")
        model.AddMultiplicationEquality(
            vol_var, [max_used_x, max_used_y, max_used_z])

        gravity_terms = ctx["gravity_terms"]

        corner_terms = sum(ctx["x"][i] + ctx["y"][i] for i in range(n)) if n > 0 else 0

        model.Minimize(vol_var + gravity_terms + corner_terms)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 8
        solver.parameters.random_seed = seed
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            placements = []
            real_l = solver.Value(max_used_x) / SCALE
            real_w = solver.Value(max_used_y) / SCALE
            real_h = solver.Value(max_used_z) / SCALE

            for i, item in enumerate(expanded):
                l_val = solver.Value(ctx["dims"][i][0]) / SCALE
                w_val = solver.Value(ctx["dims"][i][1]) / SCALE
                h_val = solver.Value(ctx["dims"][i][2]) / SCALE

                placements.append({
                    "product_id": item.product_id,
                    "x": solver.Value(ctx["x"][i]) / SCALE,
                    "y": solver.Value(ctx["y"][i]) / SCALE,
                    "z": solver.Value(ctx["z"][i]) / SCALE,
                    "length": l_val,
                    "width": w_val,
                    "height": h_val,
                    "rotation": solver.Value(ctx["rot"][i]) == 1 if self.allow_rotation else False,
                })

            return {
                "box": (real_l, real_w, real_h),
                "volume": real_l * real_w * real_h / 1000,
                "placements": placements,
                "status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "stability_enabled": enable_support,
            }

        return None

    def _shape_metric(self, ctx, strategy):
        model = ctx["model"]
        max_used_x, max_used_y, max_used_z = ctx["max_used"]
        target_l, target_w, target_h = ctx["target_l"], ctx["target_w"], ctx["target_h"]

        if strategy == "flat":
            return max_used_z, target_h

        if strategy == "tower":
            footprint = model.NewIntVar(0, target_l * target_w, "footprint")
            model.AddMultiplicationEquality(
                footprint, [max_used_x, max_used_y])
            return footprint, target_l * target_w

        if strategy == "long_x":
            cross = model.NewIntVar(0, target_w * target_h, "cross_x")
            model.AddMultiplicationEquality(
                cross, [max_used_y, max_used_z])
            return cross, target_w * target_h

        if strategy == "long_y":
            cross = model.NewIntVar(0, target_l * target_h, "cross_y")
            model.AddMultiplicationEquality(
                cross, [max_used_x, max_used_z])
            return cross, target_l * target_h

        if strategy == "cube":
            m = model.NewIntVar(0, max(target_l, target_w, target_h), "max_dim")
            model.Add(m >= max_used_x)
            model.Add(m >= max_used_y)
            model.Add(m >= max_used_z)
            return m, max(target_l, target_w, target_h)

        return None, None

    def _build_model(self, expanded, ub_x, ub_y, ub_z, min_x, min_y, min_z, enable_support=True):
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

        supported_by = {}
        raw_areas = []
        gravity_terms = 0

        if enable_support and n > 0:
            is_on_floor = [model.NewBoolVar(f"floor{i}") for i in range(n)]

            for i in range(n):
                model.Add(z[i] == 0).OnlyEnforceIf(is_on_floor[i])

                for j in range(n):
                    if i == j:
                        continue
                    supported_by[(i, j)] = model.NewBoolVar(f"sup_{i}_{j}")
                    model.Add(z[i] == z[j] + dims[j][2]).OnlyEnforceIf(
                        supported_by[(i, j)]
                    )

                supporters = [supported_by[(i, j)]
                              for j in range(n) if j != i]
                model.Add(is_on_floor[i] + sum(supporters) >= 1)

            z_sum = sum(z[i] for i in range(n))
            z_weight = SCALE * 3

            for i in range(n):
                raw_area = model.NewIntVar(0, target_l * target_w, f"ba{i}")
                model.AddMultiplicationEquality(
                    raw_area, [dims[i][0], dims[i][1]])
                raw_areas.append(raw_area)

            area_weighted_z_terms = []
            for i in range(n):
                scaled_area = model.NewIntVar(0, target_l * target_w, f"sa{i}")
                model.AddDivisionEquality(
                    scaled_area, raw_areas[i], SCALE * SCALE)

                area_z = model.NewIntVar(
                    0, target_h * target_l * target_w, f"az{i}")
                model.AddMultiplicationEquality(
                    area_z, [z[i], scaled_area])
                area_weighted_z_terms.append(area_z)

            area_weighted_z = sum(area_weighted_z_terms)
            area_z_weight = SCALE * 5

            MAX_AREA_RATIO_NUM, MAX_AREA_RATIO_DEN = 3, 2
            PENALTY_PER_PAIR = max(1, target_l * target_w * SCALE)
            big_on_small_penalty_terms = []

            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    model.Add(
                        raw_areas[i] * MAX_AREA_RATIO_DEN <= raw_areas[j] * MAX_AREA_RATIO_NUM
                    ).OnlyEnforceIf(supported_by[(i, j)])

                    area_bigger = model.NewBoolVar(f"ab_{i}_{j}")
                    model.Add(raw_areas[i] > raw_areas[j]).OnlyEnforceIf(
                        area_bigger)
                    model.Add(raw_areas[i] <= raw_areas[j]).OnlyEnforceIf(
                        area_bigger.Not())

                    both = model.NewBoolVar(f"both_{i}_{j}")
                    model.AddBoolAnd(
                        [supported_by[(i, j)], area_bigger]).OnlyEnforceIf(both)
                    model.AddBoolOr(
                        [supported_by[(i, j)].Not(), area_bigger.Not()]).OnlyEnforceIf(both.Not())

                    big_on_small_penalty_terms.append(both * PENALTY_PER_PAIR)

            big_on_small_penalty = sum(
                big_on_small_penalty_terms) if big_on_small_penalty_terms else 0

            MIN_BASE_AREA_THRESHOLD = 5000 * SCALE * SCALE
            small_support_penalty_terms = []

            for i in range(n):
                for j in range(n):
                    if i == j:
                        continue
                    is_small_base = model.NewBoolVar(f"small_base_{i}")
                    model.Add(raw_areas[i] < MIN_BASE_AREA_THRESHOLD).OnlyEnforceIf(
                        is_small_base)
                    model.Add(raw_areas[i] >= MIN_BASE_AREA_THRESHOLD).OnlyEnforceIf(
                        is_small_base.Not())

                    both_small = model.NewBoolVar(f"both_small_{i}_{j}")
                    model.AddBoolAnd(
                        [supported_by[(j, i)], is_small_base]).OnlyEnforceIf(both_small)

                    small_support_penalty_terms.append(both_small * (PENALTY_PER_PAIR // 2))

            small_support_penalty = sum(
                small_support_penalty_terms) if small_support_penalty_terms else 0

            gravity_terms = (
                z_sum * z_weight
                + area_weighted_z * area_z_weight
                + big_on_small_penalty
                + small_support_penalty
            )

        return {
            "model": model,
            "n": n,
            "x": x, "y": y, "z": z,
            "dims": dims,
            "rot": rot,
            "max_used": (max_used_x, max_used_y, max_used_z),
            "target_l": target_l, "target_w": target_w, "target_h": target_h,
            "gravity_terms": gravity_terms,
        }