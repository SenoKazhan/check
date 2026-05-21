// frontend/src/components/UploadPanel.tsx
'use client';

import type { ViewAngle, MeasurementResult } from '@/types/upload';
import type { UseImageUploadReturn } from '@/hooks/useImageUpload';

interface UploadPanelProps {
  uploadState: UseImageUploadReturn;
  onFileSelect: (view: ViewAngle, file: File) => void;
  onSubmit: () => Promise<void>;
  result?: MeasurementResult | null;
  error?: string | null;
  loading?: boolean;
}

export default function UploadPanel({
  uploadState,
  onFileSelect,
  onSubmit,
  result,
  error,
  loading = false,
}: UploadPanelProps) {
  const { files, manualRoi, isReady, setFile, clearFile } = uploadState;
  const views: ViewAngle[] = ['front', 'side', 'top'];

  return (
    <div className="mx-auto max-w-3xl rounded-xl border border-gray-100 bg-white p-6 shadow-md">
      <h2 className="mb-6 text-xl font-bold text-gray-900">
        Загрузка фотографий товара
      </h2>

      {/* Сетка загрузки файлов */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        {views.map((view) => (
          <FileUploadCard
            key={view}
            view={view}
            file={files[view]}
            hasRoi={!!manualRoi[view]}
            onSelect={(file) => onFileSelect(view, file)}
            onClear={() => clearFile(view)}
          />
        ))}
      </div>

      {/* Кнопка отправки */}
      <button
        onClick={onSubmit}
        disabled={!isReady || loading}
        className="w-full rounded-lg bg-blue-600 py-2.5 font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? 'Обработка...' : 'Начать измерение'}
      </button>

      {/* Сообщения об ошибках */}
      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Результаты измерения */}
      {result?.dimensions_mm && (
        <MeasurementResults dimensions={result.dimensions_mm} status={result.finalStatus} />
      )}
    </div>
  );
}

/**
 * Карточка загрузки файла для одного ракурса.
 */
function FileUploadCard({
  view,
  file,
  hasRoi,
  onSelect,
  onClear,
}: {
  view: ViewAngle;
  file: File | null;
  hasRoi: boolean;
  onSelect: (file: File) => void;
  onClear: () => void;
}) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      onSelect(selected);
      e.target.value = ''; // Сброс для возможности повторного выбора того же файла
    }
  };

  return (
    <div className="rounded-lg border-2 border-dashed border-gray-200 bg-gray-50/50 p-4 text-center transition hover:border-blue-400">
      <label className="mb-2 block text-sm font-medium capitalize text-gray-700">
        {view} вид
        {hasRoi && (
          <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-700">
            ROI задан
          </span>
        )}
      </label>

      <input
        type="file"
        accept="image/jpeg,image/png"
        onChange={handleChange}
        className="mb-2 block w-full cursor-pointer text-sm text-gray-500 file:mr-2 file:rounded file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-blue-700 hover:file:bg-blue-100"
      />

      {file && (
        <div className="mt-2 flex items-center justify-between">
          <p className="truncate text-xs font-medium text-gray-600">{file.name}</p>
          <button
            onClick={onClear}
            className="ml-2 text-xs text-blue-600 underline hover:text-blue-800"
          >
            Изменить
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Компонент отображения результатов измерения.
 */
function MeasurementResults({
  dimensions,
  status,
}: {
  dimensions: { length_mm?: number; width_mm?: number; height_mm?: number };
  status: string;
}) {
  const formatValue = (value?: number): string =>
    typeof value === 'number' ? value.toFixed(1) : '—';

  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
      <h3 className="mb-3 font-semibold text-gray-900">Результаты измерения</h3>

      <div className="grid grid-cols-3 gap-3 text-center">
        {[
          { label: 'Длина', value: dimensions.length_mm },
          { label: 'Ширина', value: dimensions.width_mm },
          { label: 'Высота', value: dimensions.height_mm },
        ].map((dim) => (
          <div
            key={dim.label}
            className="rounded border border-gray-100 bg-white p-3 shadow-sm"
          >
            <div className="mb-1 text-xs text-gray-500">{dim.label}</div>
            <div className="text-lg font-bold text-blue-700">
              {formatValue(dim.value)}{' '}
              <span className="text-xs font-normal text-gray-500">мм</span>
            </div>
          </div>
        ))}
      </div>

      {status === 'needs_review' && (
        <p className="mt-3 rounded border border-yellow-200 bg-yellow-50 py-2 text-center text-sm text-yellow-700">
          Требуется ручная проверка измерений
        </p>
      )}
    </div>
  );
}