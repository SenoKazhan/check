# backend/test_solver.py
from app.packing.solver import BinPackingSolver
from app.schemas.packing import Item

# 7 кубиков 100x100x100 мм
items = [
    Item(product_id=1, length_mm=100, width_mm=100, height_mm=100, quantity=7),
]

print("Запуск теста на нечётное количество кубиков (7 шт)...")
solver = BinPackingSolver(time_limit_sec=10, n_variants=3, allow_rotation=True)
results = solver.solve(items)

if not results:
    print("ОШИБКА: Решение не найдено!")
else:
    for i, res in enumerate(results):
        length, width, height = res["box"]
        vol = res["volume"]
        item_vol = 7 * (100 * 100 * 100) / 1000 # 7000 см3
        efficiency = (item_vol / vol) * 100
        
        print(f"\n--- Вариант {i+1} ---")
        print(f"Размеры коробки: {length:.0f} x {width:.0f} x {height:.0f} мм")
        print(f"Объём коробки: {vol:.0f} см3")
        print(f"Объём товаров: {item_vol:.0f} см3")
        print(f"Эффективность: {efficiency:.1f}%")
        
        if efficiency >= 99.9:
            print("[УСПЕХ] Идеальная укладка без пустот по выбранной оси!")
        elif efficiency > 80:
            print("[ХОРОШО] Компактная укладка, пустоты минимальны.")
        else:
            print("[ВНИМАНИЕ] Эффективность низкая, стоит проверить логику.")