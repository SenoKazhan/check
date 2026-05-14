"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

const VIEWS = ["front", "side", "top"] as const;
type View = typeof VIEWS[number];

interface MeasureResult {
  length_mm: number;
  width_mm: number;
  height_mm: number;
  confidence: number;
  measurement_id?: number;
}

export default function UploadPanel() {
  const [files, setFiles] = useState<Record<View, File | null>>({ front: null, side: null, top: null });
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string>("");
  const [result, setResult] = useState<MeasureResult | null>(null);

  const handleFile = (view: View, file: File | null) => {
    setFiles(prev => ({ ...prev, [view]: file }));
    setStatus("");
    setTaskId(null);
    setTaskState("");
    setResult(null);
  };

  const pollTask = useCallback(async (id: string) => {
    try {
      const { data } = await api.get(`/api/v1/tasks/${id}`);
      setTaskState(data.state);

      if (data.state === "SUCCESS") {
        setResult(data.result);
        setStatus("✅ Измерение завершено. Данные готовы к упаковке.");
        setLoading(false);
      } else if (data.state === "FAILURE") {
        setStatus(`❌ Ошибка обработки: ${data.error || "Сбой воркера"}`);
        setLoading(false);
      } else {
        setStatus("⏳ Обработка изображений нейросетью...");
      }
    } catch {
      
    }
  }, []);

  useEffect(() => {
    if (!taskId || taskState === "SUCCESS" || taskState === "FAILURE") return;
    const interval = setInterval(() => pollTask(taskId), 2000);
    return () => clearInterval(interval);
  }, [taskId, taskState, pollTask]);

  const handleSubmit = async () => {
    if (!files.front || !files.side || !files.top) {
      setStatus("⚠️ Выберите все 3 изображения (Front, Side, Top)");
      return;
    }

    setLoading(true);
    setStatus("📤 Загрузка и валидация...");
    setTaskId(null);
    setTaskState("");
    setResult(null);

    const formData = new FormData();
    formData.append("files", files.front);
    formData.append("files", files.side);
    formData.append("files", files.top);

    try {
      const { data } = await api.post("/api/v1/measurements/start", formData);
      setTaskId(data.task_id);
      setTaskState("PENDING");
      setStatus("Задача поставлена в очередь. Ожидание обработки...");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setStatus(`❌ Ошибка: ${message}`);
      } finally {
    if (taskState !== "SUCCESS" && taskState !== "FAILURE") {
      setLoading(false);
    }
  }
  
  };

  return ( // ← ✅ return начинается здесь
    <div className="max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-md border border-gray-100">
      <h2 className="text-xl font-bold mb-4 text-gray-800">Загрузка фотографий товара</h2>
      
      <div className="grid grid-cols-3 gap-4 mb-6">
        {VIEWS.map(view => (
          <div key={view} className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors bg-gray-50/50">
            <label className="block text-sm font-medium mb-2 capitalize text-gray-700">{view} вид</label>
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={e => handleFile(view, e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
            />
            {files[view] && <p className="mt-2 text-xs text-green-600 truncate font-medium">{files[view]!.name}</p>}
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

      {result && (
        <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200 animate-in fade-in slide-in-from-bottom-2 duration-300">
          <h3 className="font-semibold text-gray-800 mb-3">📏 Результаты измерения</h3>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Длина</div>
              <div className="text-lg font-bold text-blue-700">{result.length_mm.toFixed(1)} <span className="text-xs font-normal">мм</span></div>
            </div>
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Ширина</div>
              <div className="text-lg font-bold text-blue-700">{result.width_mm.toFixed(1)} <span className="text-xs font-normal">мм</span></div>
            </div>
            <div className="bg-white p-3 rounded shadow-sm">
              <div className="text-xs text-gray-500">Высота</div>
              <div className="text-lg font-bold text-blue-700">{result.height_mm.toFixed(1)} <span className="text-xs font-normal">мм</span></div>
            </div>
          </div>
          <div className="mt-3 flex justify-between items-center text-xs text-gray-500">
            <span>Уверенность модели: <b className={result.confidence > 0.4 ? "text-green-600" : "text-orange-500"}>{(result.confidence * 100).toFixed(1)}%</b></span>
            <button 
              onClick={() => { /* Роутинг на страницу упаковки */ }}
              className="px-4 py-1.5 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition font-medium"
            >
              📦 Перейти к упаковке
            </button>
          </div>
        </div>
      )}
    </div>
  );
} 