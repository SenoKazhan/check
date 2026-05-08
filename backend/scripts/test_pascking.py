"""
Тестовый скрипт для проверки работы решателя упаковки (3D Bin Packing).
Запускать из папки backend: python -m scripts.test_packing
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.schemas.packing import Item
from app.packing.solver import BinPackingSolver


def verify_packing(box_size: tuple, placements: List[Dict]) -> bool:
    """
    Простая проверка корректности упаковки:
    1. Товары не выходят за границы коробки.
    2. Товары не пересекаются друг с другом.
    """
    box_l, box_w, box_h = box_size
    n = len(placements)
    
    # 1. Проверка границ
    for i, p in enumerate(placements):
        if (p['x'] < -1e-6 or p['y'] < -1e-6 or p['z'] < -1e-6 or
            p['x'] + p['length'] > box_l + 1e-6 or
            p['y'] + p['width'] > box_w + 1e-6 or
            p['z'] + p['height'] > box_h + 1e-6):
            print(f"  ⚠️ Товар {i} выходит за границы коробки!")
            return False
        
        # 2. Проверка пересечений (O(N^2), для N<20 это мгновенно)
        for j in range(i + 1, n):
            q = placements[j]
            # Условие НЕпересечения: хотя бы одна ось разделена
            no_overlap = (
                p['x'] + p['length'] <= q['x'] + 1e-6 or # p слева от q
                q['x'] + q['length'] <= p['x'] + 1e-6 or # q слева от p
                p['y'] + p['width'] <= q['y'] + 1e-6 or  # p сзади q
                q['y'] + q['width'] <= p['y'] + 1e-6 or  # q сзади p
                p['z'] + p['height'] <= q['z'] + 1e-6 or # p ниже q
                q['z'] + q['height'] <= p['z'] + 1e-6    # q ниже p
            )
            if not no_overlap:
                print(f"  ⚠️ Пересечение товаров {i} и {j}!")
                return False
                
    return True


def export_results_to_json(results: List[Dict], filename: str):
    """Экспорт результатов в JSON файл."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"\n💾 Результаты сохранены в {filename}")


def print_solution(result: dict, index: int):
    print(f"\n📦 Вариант {index + 1}:")
    print(f"  Коробка: {result['box'][0]:.1f} x {result['box'][1]:.1f} x {result['box'][2]:.1f} мм")
    print(f"  Объём: {result['volume']:.0f} см³")
    
    if 'placements' in result:
        print(f"  Количество размещений: {len(result['placements'])}")
        
        # Расчет эффективности заполнения
        total_item_vol = sum(p['length'] * p['width'] * p['height'] for p in result['placements'])
        box_vol_mm3 = result['box'][0] * result['box'][1] * result['box'][2]
        efficiency = (total_item_vol / box_vol_mm3) * 100 if box_vol_mm3 > 0 else 0
        print(f"  📊 Эффективность заполнения: {efficiency:.1f}%")

        # Вывод первых 5 товаров для примера
        for j, p in enumerate(result['placements'][:5]):
            rot_str = " (поворот)" if p.get('rotation', False) else ""
            print(f"    {j+1}. Товар ID {p['product_id']}: "
                  f"поз ({p['x']:.1f}, {p['y']:.1f}, {p['z']:.1f}), "
                  f"разм ({p['length']:.1f}x{p['width']:.1f}x{p['height']:.1f}){rot_str}")
        
        if len(result['placements']) > 5:
            print(f"    ... и ещё {len(result['placements']) - 5} размещений")


def main():
    print("🚀 Тестирование BinPackingSolver (CP-SAT)...")
    
    # Тестовые данные: смесь больших, средних и мелких товаров
    items = [
        Item(product_id=1, length_mm=300, width_mm=200, height_mm=150, quantity=1),  # Большой
        Item(product_id=2, length_mm=150, width_mm=100, height_mm=80, quantity=2),   # Средний
        Item(product_id=3, length_mm=50, width_mm=50, height_mm=50, quantity=10),    # Мелкий (кубики)
    ]
    
    print("📦 Входные данные:")
    total_items = sum(i.quantity for i in items)
    for item in items:
        print(f"  - ID {item.product_id}: {item.length_mm}x{item.width_mm}x{item.height_mm} мм, кол-во: {item.quantity}")
    print(f"  Всего единиц товара: {total_items}")

    # Инициализация решателя
    # time_limit_sec=15 достаточно для ~15-20 товаров на современном CPU
    solver = BinPackingSolver(time_limit_sec=15, n_variants=3, allow_rotation=True)
    
    try:
        results = solver.solve(items)
    except Exception as e:
        print(f"❌ Ошибка при решении: {e}")
        import traceback
        traceback.print_exc()
        return

    if not results:
        print("❌ Решения не найдены за отведенное время.")
        return
        
    print(f"✅ Найдено вариантов: {len(results)}")
    
    all_valid = True
    for i, res in enumerate(results):
        print_solution(res, i)
        
        # Верификация геометрии
        is_valid = verify_packing(res['box'], res.get('placements', []))
        if is_valid:
            print(f"  ✅ Геометрическая целостность подтверждена")
        else:
            print(f"  ❌ ОШИБКА ГЕОМЕТРИИ!")
            all_valid = False
            
    if all_valid:
        print("\n🎉 Все варианты успешно прошли верификацию!")
        export_results_to_json(results, "packing_results_test.json")
    else:
        print("\n⚠️ Внимание: обнаружены ошибки в упаковке.")

if __name__ == "__main__":
    main()