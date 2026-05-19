import sys
import cv2
from app.cv.aruco_measure import measure_object_auto
from app.cv.optimized_wrapper import DepthAnythingV2OpenVINO
from app.core.config import settings

def test_single(image_path: str, marker_size_m: float = 0.055):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        print(f"Не удалось прочитать: {image_path}")
        return

    model = DepthAnythingV2OpenVINO(
        ir_path=settings.cv_model_ir_path,
        model_size=settings.cv_model_size,
        metric=True,
        scene_type=settings.cv_scene_type,
        device="CPU",
    )

    depth_map = model.estimate(image_bgr)

    measurements, annotated, mask = measure_object_auto(
        image_bgr=image_bgr,
        marker_size_m=marker_size_m,
        depth_map=depth_map,
        object_label="Test",
    )

    if measurements:
        print(f"Ширина: {measurements['width_m']*1000:.1f} мм")
        print(f"Высота: {measurements['height_m']*1000:.1f} мм")
        print(f"Глубина: {measurements.get('depth_m', 'N/A')}")
        cv2.imwrite("result_annotated.jpg", annotated)
        print("Результат сохранён: result_annotated.jpg")
    else:
        print("Измерение не удалось")

if __name__ == "__main__":
    test_single(sys.argv[1])