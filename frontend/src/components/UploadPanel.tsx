"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";

const VIEWS = ["front", "side", "top"] as const;
type View = typeof VIEWS[number];

const formatDimension = (value: number | undefined | null): string => {
  // Проверяем, что значение существует и является числом
  if (value === undefined || value === null || typeof value !== 'number' || isNaN(value)) {
    return '—';
  }
  return value.toFixed(1);
};

interface MeasureResult {
  status: string;
  measurement_id: number;
  final_status: string;
  confidence: number;
  dimensions_mm: {
    length_mm?: number;
    width_mm?: number;  
    height_mm?: number;  
  };
}

// Вспомогательная функция для центрирования кропа
function centerAspectCrop(
  mediaWidth: number,
  mediaHeight: number,
  aspect: number,
): Crop {
  return centerCrop(
    makeAspectCrop(
      {
        unit: "%",
        width: 90,
      },
      aspect,
      mediaWidth,
      mediaHeight,
    ),
    mediaWidth,
    mediaHeight,
  );
}

export default function UploadPanel() {
  const [files, setFiles] = useState<Record<View, File | null>>({
    front: null,
    side: null,
    top: null,
  });
  
  const [showCropper, setShowCropper] = useState(false);
  const [cropView, setCropView] = useState<View | null>(null);
  const [imgSrc, setImgSrc] = useState("");
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const imgRef = useRef<HTMLImageElement>(null);
  const [manualRoi, setManualRoi] = useState<Record<View, string | null>>({
    front: null,
    side: null,
    top: null,
  });

  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string>("");
  const [result, setResult] = useState<MeasureResult | null>(null);

  // --- Логика Кроппера (ROI) ---
  const handleSelectImageForCrop = (view: View, file: File | null) => {
    if (!file) return;
    setFiles((prev) => ({ ...prev, [view]: file }));
    
    const objectUrl = URL.createObjectURL(file);
    setImgSrc(objectUrl);
    setCropView(view);
    setShowCropper(true);
    setCrop(undefined);
    setCompletedCrop(undefined);
  };

  const onImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const { width, height } = e.currentTarget;
    const crop = centerAspectCrop(width, height, 1);
    setCrop(crop);
  };

  const handleCropComplete = () => {
    if (!cropView || !imgRef.current || !completedCrop) return;

    const { naturalWidth, naturalHeight } = imgRef.current;

    let x: number, y: number, w: number, h: number;
    
    if (completedCrop.unit === "%") {
      x = (completedCrop.x / 100) * naturalWidth;
      y = (completedCrop.y / 100) * naturalHeight;
      w = (completedCrop.width / 100) * naturalWidth;
      h = (completedCrop.height / 100) * naturalHeight;
    } else {
      x = completedCrop.x;
      y = completedCrop.y;
      w = completedCrop.width;
      h = completedCrop.height;
    }

    const x1 = Math.round(x);
    const y1 = Math.round(y);
    const x2 = Math.round(x + w);
    const y2 = Math.round(y + h);

    const roiString = `${x1},${y1},${x2},${y2}`;
    setManualRoi((prev) => ({ ...prev, [cropView]: roiString }));
    
    setStatus(`✅ Область для ${cropView} выделена`);
    handleCloseCropper();
  };

  const handleCloseCropper = () => {
    setShowCropper(false);
    setImgSrc("");
    setCropView(null);
  };

  // --- Основная логика загрузки ---
  const pollTask = useCallback(async (id: string) => {
    try {
      const { data } = await api.get(`/api/v1/tasks/${id}`);
      setTaskState(data.state);
      if (data.state === "SUCCESS") {
        setResult(data.result);
        setStatus("✅ Измерение завершено.");
        setLoading(false);
      } else if (data.state === "FAILURE") {
        setStatus(`❌ Ошибка: ${data.error || "Сбой"}`);
        setLoading(false);
      } else {
        setStatus("⏳ Обработка...");
      }
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!taskId || taskState === "SUCCESS" || taskState === "FAILURE") return;
    const interval = setInterval(() => pollTask(taskId), 2000);
    return () => clearInterval(interval);
  }, [taskId, taskState, pollTask]);

  const handleSubmit = async () => {
    if (!files.front || !files.side || !files.top) {
      setStatus("⚠️ Выберите все 3 изображения");
      return;
    }
    setLoading(true);
    setStatus("📤 Загрузка...");
    setTaskId(null);

    const formData = new FormData();
    formData.append("files", files.front);
    formData.append("files", files.side);
    formData.append("files", files.top);

    const roiToUse = manualRoi.front; 

    try {
      const { data } = await api.post("/api/v1/measurements/start", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        params: {
          manual_roi: roiToUse || undefined,
        },
        withCredentials: true,
      });
      setTaskId(data.task_id);
      setTaskState("PENDING");
      setStatus("Задача поставлена в очередь.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Ошибка";
      setStatus(`❌ ${message}`);
      setLoading(false);
    }
  };

  const getRoiIndicator = (view: View) => {
    if (manualRoi[view]) {
      return <span className="ml-2 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">ROI задан</span>;
    }
    return null;
  };

  return (
    <div className="max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-md border border-gray-100">
      <h2 className="text-xl font-bold mb-4 text-gray-800">Загрузка фотографий товара</h2>

      {showCropper && cropView && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full flex flex-col max-h-[90vh]">
            <div className="p-4 border-b flex justify-between items-center">
              <h3 className="text-lg font-semibold">Выделите область интереса ({cropView})</h3>
              <button onClick={handleCloseCropper} className="text-gray-500 hover:text-red-500 text-xl font-bold">×</button>
            </div>
            
            <div className="p-4 overflow-auto flex-1 flex justify-center bg-gray-100">
              <ReactCrop
                crop={crop}
                onChange={(_: Crop, percentCrop: Crop) => setCrop(percentCrop)}
                onComplete={(c: Crop) => setCompletedCrop(c)}
                aspect={undefined}
                className="max-h-[60vh]"
              >
                <img
                  ref={imgRef}
                  src={imgSrc}
                  onLoad={onImageLoad}
                  className="max-h-[60vh] object-contain"
                  alt="Crop preview"
                />
              </ReactCrop>
            </div>

            <div className="p-4 border-t flex justify-end gap-3">
              <button
                onClick={handleCloseCropper}
                className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
              >
                Отмена
              </button>
              <button
                onClick={handleCropComplete}
                disabled={!completedCrop}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                Сохранить область
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4 mb-6">
        {VIEWS.map((view) => (
          <div key={view} className="relative border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors bg-gray-50/50">
            <label className="block text-sm font-medium mb-2 capitalize text-gray-700">
              {view} вид {getRoiIndicator(view)}
            </label>
            
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={(e) => handleSelectImageForCrop(view, e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer mb-2"
            />
            
            {files[view] && (
              <button
                onClick={() => handleSelectImageForCrop(view, files[view])}
                className="text-xs text-blue-600 hover:text-blue-800 underline"
              >
                Изменить область (ROI)
              </button>
            )}
            
            {files[view] && <p className="mt-1 text-xs text-green-600 truncate font-medium">{files[view]!.name}</p>}
          </div>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm"
      >
        {loading ? "⏳ Отправка..." : "🚀 Начать измерение"}
      </button>

      {status && (
        <div className={`mt-4 p-3 rounded-lg text-sm border ${
          status.startsWith("✅") ? "bg-green-50 border-green-200 text-green-800" :
          status.startsWith("❌") ? "bg-red-50 border-red-200 text-red-800" :
          "bg-blue-50 border-blue-200 text-blue-800"
        }`}>
          {status}
        </div>
      )}

      {result && result.dimensions_mm && (
        <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
          <h3 className="font-semibold text-gray-800 mb-3">📏 Результаты</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Длина</div>
              <div className="text-lg font-bold text-blue-700">
                {(() => {
                  const val = result.dimensions_mm?.length_mm;
                  return typeof val === 'number' ? val.toFixed(1) : '—';
                })()}{' '}
                <span className="text-xs font-normal">мм</span>
              </div>
            </div>
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Ширина</div>
              <div className="text-lg font-bold text-blue-700">
                {(() => {
                  const val = result.dimensions_mm?.width_mm;
                  return typeof val === 'number' ? val.toFixed(1) : '—';
                })()}{' '}
                <span className="text-xs font-normal">мм</span>
              </div>
            </div>
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Высота</div>
              <div className="text-lg font-bold text-blue-700">
                {(() => {
                  const val = result.dimensions_mm?.height_mm;
                  return typeof val === 'number' ? val.toFixed(1) : '—';
                })()}{' '}
                <span className="text-xs font-normal">мм</span>
              </div>
            </div>
          </div>
          {result.final_status === 'needs_review' && (
            <p className="mt-3 text-sm text-yellow-600 text-center bg-yellow-50 py-1 rounded">
              ⚠️ Требуется ручная проверка измерений
            </p>
          )}
        </div>
      )}
    </div> 
  );
}