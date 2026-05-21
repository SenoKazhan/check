/**
 * Компонент модального окна для выделения области интереса (ROI).
 * Вынесен в отдельный модуль для повторного использования и тестирования.
 */

'use client';

import { useState, useRef } from 'react';
import ReactCrop, { type Crop } from 'react-image-crop';
import 'react-image-crop/dist/ReactCrop.css';
import type { ViewAngle } from '@/types/upload';

interface ImageCropperProps {
  view: ViewAngle;
  file: File;
  onClose: () => void;
  onCropComplete: (roi: string) => void;
}

export default function ImageCropper({ view, file, onClose, onCropComplete }: ImageCropperProps) {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const imgRef = useRef<HTMLImageElement>(null);

  // Инициализация: создание объектного URL для изображения
  useState(() => {
    const url = URL.createObjectURL(file);
    setImgSrc(url);
    return () => URL.revokeObjectURL(url);
  });

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const { width, height } = e.currentTarget;
    // Центрированный кроп 90% от изображения
    setCrop({
      unit: '%',
      x: 5,
      y: 5,
      width: 90,
      height: 90,
    });
  };

  const handleConfirm = () => {
    if (!completedCrop || !imgRef.current) return;

    const { naturalWidth, naturalHeight } = imgRef.current;
    const { x, y, width, height, unit } = completedCrop;

    // Конвертация координат в пиксели
    const coords =
      unit === '%'
        ? {
            x1: Math.round((x / 100) * naturalWidth),
            y1: Math.round((y / 100) * naturalHeight),
            x2: Math.round(((x + width) / 100) * naturalWidth),
            y2: Math.round(((y + height) / 100) * naturalHeight),
          }
        : {
            x1: Math.round(x),
            y1: Math.round(y),
            x2: Math.round(x + width),
            y2: Math.round(y + height),
          };

    const roi = `${coords.x1},${coords.y1},${coords.x2},${coords.y2}`;
    onCropComplete(roi);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="flex w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-xl">
        {/* Заголовок */}
        <div className="flex items-center justify-between border-b p-4">
          <h3 className="text-lg font-semibold">
            Выделите область интереса ({view})
          </h3>
          <button
            onClick={onClose}
            className="text-2xl leading-none text-gray-400 transition hover:text-red-500"
            aria-label="Закрыть"
          >
            &times;
          </button>
        </div>

        {/* Область кроппинга */}
        <div className="flex flex-1 items-center justify-center bg-gray-50 p-4">
          <ReactCrop
            crop={crop}
            onChange={(_, percentCrop) => setCrop(percentCrop)}
            onComplete={setCompletedCrop}
            aspect={undefined}
            className="max-h-[60vh]"
          >
            <img
              ref={imgRef}
              src={imgSrc}
              onLoad={handleImageLoad}
              alt="Preview for cropping"
              className="max-h-[60vh] object-contain"
            />
          </ReactCrop>
        </div>

        {/* Кнопки действий */}
        <div className="flex justify-end gap-3 border-t p-4">
          <button
            onClick={onClose}
            className="rounded bg-gray-200 px-4 py-2 text-sm transition hover:bg-gray-300"
          >
            Отмена
          </button>
          <button
            onClick={handleConfirm}
            disabled={!completedCrop}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Сохранить область
          </button>
        </div>
      </div>
    </div>
  );
}