'use client';

import { useState } from 'react';
import UploadPanel from '@/components/UploadPanel';
import ImageCropper from '@/components/ImageCropper';
import { useImageUpload } from '@/hooks/useImageUpload';
import type { ViewAngle } from '@/types/upload';

export default function MeasurePage() {
  const upload = useImageUpload();
  const [cropping, setCropping] = useState<{ view: ViewAngle; file: File } | null>(null);

  const handleFileSelect = (view: ViewAngle, file: File) => {
    upload.setFile(view, file);
    setCropping({ view, file });
  };

  const handleCropComplete = (roi: string) => {
    if (cropping) {
      upload.setRoi(cropping.view, roi);
      setCropping(null);
    }
  };

  const handleSubmit = async () => {
    try {
      await upload.submit(); // ← Вызов отправки в API
      // Опционально: показать уведомление или редирект
    } catch (error) {
      console.error('Ошибка измерения:', error);
      // UploadPanel уже покажет ошибку через upload.error
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="mx-auto max-w-4xl px-4">
        <h1 className="mb-8 text-center text-3xl font-bold text-gray-900">
          Измерение габаритов
        </h1>

        <UploadPanel
          uploadState={upload}
          onFileSelect={handleFileSelect}
          onSubmit={handleSubmit}  // ← Передаём реальную функцию
        />

        {cropping && (
          <ImageCropper
            view={cropping.view}
            file={cropping.file}
            onClose={() => setCropping(null)}
            onCropComplete={handleCropComplete}
          />
        )}
      </div>
    </div>
  );
}