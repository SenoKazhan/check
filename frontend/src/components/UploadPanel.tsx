"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const VIEWS = ["front", "side", "top"] as const;
type View = typeof VIEWS[number];

export default function UploadPanel() {
  const [files, setFiles] = useState<Record<View, File | null>>({ front: null, side: null, top: null });
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const handleFile = (view: View, file: File | null) => {
    setFiles(prev => ({ ...prev, [view]: file }));
    setStatus("");
  };

  const handleSubmit = async () => {
    if (!files.front || !files.side || !files.top) {
      setStatus("Выберите все 3 изображения (Front, Side, Top)");
      return;
    }

    setLoading(true);
    setStatus("Валидация и загрузка...");

    const formData = new FormData();
    formData.append("front", files.front);
    formData.append("side", files.side);
    formData.append("top", files.top);

    try {
      const res = await api.post("/upload/measure", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setStatus(`✅ Задача отправлена. ID: ${res.data.task_id}. Результаты появятся в логах Celery.`);
    } catch (err: any) {
      setStatus(`❌ Ошибка: ${err.response?.data?.detail || "Не удалось загрузить файлы"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6 bg-white rounded-xl shadow-md">
      <h2 className="text-xl font-bold mb-4 text-gray-800">Загрузка фотографий товара</h2>
      <div className="grid grid-cols-3 gap-4 mb-6">
        {VIEWS.map(view => (
          <div key={view} className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-blue-400 transition-colors">
            <label className="block text-sm font-medium mb-2 capitalize text-gray-700">{view} вид</label>
            <input
              type="file"
              accept="image/jpeg,image/png"
              onChange={e => handleFile(view, e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
            />
            {files[view] && <p className="mt-2 text-xs text-green-600 truncate">{files[view]!.name}</p>}
          </div>
        ))}
      </div>
      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Отправка..." : "Начать измерение"}
      </button>
      {status && <p className={`mt-4 text-sm ${status.startsWith("✅") ? "text-green-700" : "text-red-600"}`}>{status}</p>}
    </div>
  );
}