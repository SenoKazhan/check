/**
 * Хук для управления загрузкой и обработкой изображений.
 * Инкапсулирует логику работы с файлами и ROI, обеспечивает очистку ресурсов.
 */

import { useState, useCallback, useEffect } from 'react';
import type { ViewAngle, UploadState } from '@/types/upload';

interface UseImageUploadReturn extends UploadState {
  setFile: (view: ViewAngle, file: File | null) => void;
  setRoi: (view: ViewAngle, roi: string | null) => void;
  clearFile: (view: ViewAngle) => void;
  submit: () => Promise<void>;
  reset: () => void;
  isReady: boolean;
}

export function useImageUpload(): UseImageUploadReturn {
  const [state, setState] = useState<UploadState>({
    files: { front: null, side: null, top: null },
    manualRoi: { front: null, side: null, top: null },
  });

  // ✅ isReady объявлен ПЕРЕД функциями, которые его используют
  const isReady = Object.values(state.files).every((file) => file !== null);

  // Очистка объектных URL для предотвращения утечек памяти
  useEffect(() => {
    return () => {
      Object.values(state.files).forEach((file) => {
        if (file) URL.revokeObjectURL(URL.createObjectURL(file));
      });
    };
  }, [state.files]);

  const setFile = useCallback((view: ViewAngle, file: File | null) => {
    setState((prev) => ({
      ...prev,
      files: { ...prev.files, [view]: file },
    }));
  }, []);

  const setRoi = useCallback((view: ViewAngle, roi: string | null) => {
    setState((prev) => ({
      ...prev,
      manualRoi: { ...prev.manualRoi, [view]: roi },
    }));
  }, []);

  const clearFile = useCallback((view: ViewAngle) => {
    setState((prev) => {
      const file = prev.files[view];
      if (file) URL.revokeObjectURL(URL.createObjectURL(file));
      return {
        ...prev,
        files: { ...prev.files, [view]: null },
        manualRoi: { ...prev.manualRoi, [view]: null },
      };
    });
  }, []);

  // ✅ Теперь isReady доступен в замыкании и в массиве зависимостей
  const submit = useCallback(async () => {
    if (!isReady) {
      throw new Error('Выберите все 3 изображения');
    }
    // Здесь будет реальная логика отправки на бэкенд
    console.log('Submitting:', state.files, state.manualRoi);
  }, [isReady, state.files, state.manualRoi]);

  const reset = useCallback(() => {
    setState({
      files: { front: null, side: null, top: null },
      manualRoi: { front: null, side: null, top: null },
    });
  }, []);

  return {
    ...state,
    setFile,
    setRoi,
    clearFile,
    submit,
    reset,
    isReady,
  };
}