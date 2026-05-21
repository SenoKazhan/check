import cv2
from pyzbar.pyzbar import decode
import sys

def scan_image(image_path):
    """
    Сканирует изображение на наличие QR-кодов и штрихкодов.
    """
    print(f"🔍 Читаю изображение: {image_path}")
    
    # 1. Загрузка изображения
    image = cv2.imread(image_path)
    if image is None:
        print("❌ Ошибка: Не удалось загрузить изображение. Проверьте путь.")
        return

    # 2. Декодирование всех кодов (QR + Штрихкоды)
    # pyzbar автоматически определяет тип символа
    decoded_objects = decode(image)

    if not decoded_objects:
        print("⚠️ Коды не обнаружены.")
        print("Советы:")
        print("- Убедитесь, что код четкий и хорошо освещен.")
        print("- Попробуйте увеличить масштаб кода на фото.")
        print("- Проверьте, нет ли бликов на поверхности.")
        return

    print(f"\n✅ Найдено объектов: {len(decoded_objects)}\n")
    
    for i, obj in enumerate(decoded_objects):
        print(f"--- Объект #{i+1} ---")
        print(f"Тип:          {obj.type}")
        print(f"Данные:       {obj.data.decode('utf-8')}")
        print(f"Позиция:      {obj.polygon}")
        print(f"Прямоугольник: {obj.rect}")
        print("------------------")

if __name__ == "__main__":
    # Если имя файла передано как аргумент, используем его, иначе берем default
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "k.png" # Замените на имя вашего файла
        
    scan_image(filename)