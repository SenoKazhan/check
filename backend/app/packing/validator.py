# app/packing/validator.py
from typing import List, Dict, Tuple


def verify_packing(box_size: tuple, placements: List[Dict]) -> bool:
    """
    Проверяет корректность упаковки.

    Args:
        box_size: (length, width, height) коробки в мм
        placements: список размещений, каждое с ключами:
            x, y, z, length, width, height

    Returns:
        True, если все товары внутри коробки и не пересекаются.
    """
    box_l, box_w, box_h = box_size
    n = len(placements)

    # Проверка границ и форматов
    for i, p in enumerate(placements):
        # Границы коробки
        if (p['x'] < 0 or p['y'] < 0 or p['z'] < 0 or
            p['x'] + p['length'] > box_l + 1e-6 or
            p['y'] + p['width'] > box_w + 1e-6 or
            p['z'] + p['height'] > box_h + 1e-6):
            print(f"❌ Товар {i} выходит за границы коробки")
            return False

        # Проверка с каждым следующим
        for j in range(i+1, n):
            q = placements[j]
            if (p['x'] < q['x'] + q['length'] and
                p['x'] + p['length'] > q['x'] and
                p['y'] < q['y'] + q['width'] and
                p['y'] + p['width'] > q['y'] and
                p['z'] < q['z'] + q['height'] and
                p['z'] + p['height'] > q['z']):
                print(f"❌ Пересечение товаров {i} и {j}")
                return False
    return True


def check_support_constraint(placements: List[Dict], tolerance_mm: float = 0.15) -> Tuple[bool, List[str], int]:
    """
    Проверяет, что каждый предмет имеет опору снизу.

    Returns:
        (ok, issues, supported_count)
        ok — True если все предметы поддерживаются
        issues — список строк с описанием проблем
        supported_count — количество поддерживаемых предметов
    """
    n = len(placements)
    issues = []
    supported_count = 0

    for i, p in enumerate(placements):
        x1, y1, z1 = p['x'], p['y'], p['z']

        # На полу?
        if abs(z1) < tolerance_mm:
            supported_count += 1
            continue

        # Ищем опору снизу
        found_support = False
        for j, q in enumerate(placements):
            if i == j:
                continue
            top_of_j = q['z'] + q['height']

            if abs(z1 - top_of_j) < tolerance_mm:
                # Проверяем XY-пересечение
                overlap_x = max(0, min(x1 + p['length'], q['x'] + q['length']) - max(x1, q['x']))
                overlap_y = max(0, min(y1 + p['width'],  q['y'] + q['width'])  - max(y1, q['y']))

                if overlap_x > 0.01 and overlap_y > 0.01:
                    found_support = True
                    break

        if found_support:
            supported_count += 1
        else:
            issues.append(
                f"Предмет {i} (id={p.get('item_id', p.get('product_id'))}, "
                f"{p['length']:.0f}x{p['width']:.0f}x{p['height']:.0f} "
                f"at z={p['z']:.1f}) не имеет опоры снизу"
            )

    return len(issues) == 0, issues, supported_count


def check_area_stability(placements: List[Dict], max_ratio: float = 1.5,
                         tolerance_mm: float = 0.15) -> Tuple[bool, List[str]]:
    """
    Проверяет, что нет явных нарушений "крупный на мелком".

    Args:
        max_ratio: максимально допустимое отношение площадей
                   (area_top / area_bottom <= max_ratio)

    Returns:
        (ok, issues)
    """
    issues = []

    for i, p in enumerate(placements):
        for j, q in enumerate(placements):
            if i == j:
                continue

            top_j = q['z'] + q['height']
            if abs(p['z'] - top_j) < tolerance_mm:
                # Проверяем XY-пересечение
                overlap_x = max(0, min(p['x'] + p['length'], q['x'] + q['length']) - max(p['x'], q['x']))
                overlap_y = max(0, min(p['y'] + p['width'],  q['y'] + q['width'])  - max(p['y'], q['y']))

                if overlap_x > 0.01 and overlap_y > 0.01:
                    base_i = p['length'] * p['width']
                    base_j = q['length'] * q['width']

                    if base_i > base_j * max_ratio:
                        issues.append(
                            f"Предмет {i} (base={base_i:.0f}) стоит на предмете "
                            f"{j} (base={base_j:.0f}), ratio={base_i/base_j:.1f} > {max_ratio}"
                        )

    return len(issues) == 0, issues


def validate_stability(placements: List[Dict], max_area_ratio: float = 1.5) -> Dict:
    """
    Комплексная проверка стабильности упаковки.

    Returns:
        dict с результатами проверок
    """
    ok_support, issues_support, sup_count = check_support_constraint(placements)
    ok_area, issues_area = check_area_stability(placements, max_ratio=max_area_ratio)

    n = len(placements)
    return {
        "stable": ok_support and ok_area,
        "support": {
            "ok": ok_support,
            "supported_count": sup_count,
            "total": n,
            "issues": issues_support,
        },
        "area_stability": {
            "ok": ok_area,
            "max_allowed_ratio": max_area_ratio,
            "issues": issues_area,
        },
    }