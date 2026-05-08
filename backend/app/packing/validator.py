# app/packing/validator.py
from typing import List, Dict

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