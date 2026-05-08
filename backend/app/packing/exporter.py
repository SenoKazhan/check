# app/packing/exporter.py
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

def export_results_to_json(results: List[Dict], filename: str = None) -> str:
    """Сохраняет результаты упаковки в JSON файл."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"packing_results_{timestamp}.json"
    
    # Преобразуем для JSON (если есть несериализуемые объекты)
    export_data = {
        "export_time": datetime.now().isoformat(),
        "solver_config": {
            "time_limit_sec": results[0].get('_solver_time_limit', 100),
            "n_variants": len(results),
            "allow_rotation": results[0].get('_allow_rotation', True)
        },
        "solutions": []
    }
    
    for res in results:
        solution = {
            "box_mm": res['box'],
            "volume_cm3": res['volume'] / 1000,
            "placements": []
        }
        for p in res.get('placements', []):
            solution['placements'].append({
                "product_id": p['product_id'],
                "position_mm": (p['x'], p['y'], p['z']),
                "dimensions_mm": (p['length'], p['width'], p['height']),
                "rotated": p.get('rotation', False)
            })
        export_data['solutions'].append(solution)
    
    output_path = Path(filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Результаты экспортированы в {output_path.absolute()}")
    return str(output_path)