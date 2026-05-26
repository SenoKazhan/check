// frontend/src/hooks/useImageUpload.ts
import { useState, useCallback, useEffect } from 'react';
import { api } from '@/lib/api';
import type { ViewAngle, MeasurementResult, UploadState } from '@/types/upload';

interface UseImageUploadReturn extends UploadState {
  setFile: (view: ViewAngle, file: File | null) => void;
  setRoi: (view: ViewAngle, roi: string | null) => void;
  clearFile: (view: ViewAngle) => void;
  submit: () => Promise<void>;
  reset: () => void;
  isReady: boolean;
  loading: boolean;
  error: string | null;
  result: MeasurementResult | null;
}

export function useImageUpload(): UseImageUploadReturn {
  const [state, setState] = useState<UploadState>({
    files: { front: null, side: null, top: null },
    manualRoi: { front: null, side: null, top: null },
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MeasurementResult | null>(null);

  const isReady = Object.values(state.files).every((file) => file !== null);

  useEffect(() => {
    return () => {
      Object.values(state.files).forEach((file) => {
        if (file) URL.revokeObjectURL(URL.createObjectURL(file));
      });
    };
  }, [state.files]);

  const setFile = useCallback((view: ViewAngle, file: File | null) => {
    setState((prev) => ({ ...prev, files: { ...prev.files, [view]: file } }));
  }, []);

  const setRoi = useCallback((view: ViewAngle, roi: string | null) => {
    setState((prev) => ({ ...prev, manualRoi: { ...prev.manualRoi, [view]: roi } }));
  }, []);

  const clearFile = useCallback((view: ViewAngle) => {
    setState((prev) => ({
      ...prev,
      files: { ...prev.files, [view]: null },
      manualRoi: { ...prev.manualRoi, [view]: null },
    }));
  }, []);

  const submit = useCallback(async () => {
    if (!isReady) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      if (state.files.front) formData.append('files', state.files.front);
      if (state.files.side) formData.append('files', state.files.side);
      if (state.files.top) formData.append('files', state.files.top);

      const { data } = await api.post<MeasurementResult>('/api/v1/measurements/start', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setResult(data);
    } catch (err: unknown) {
      const message = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : 'Ошибка сети или сервера';
      setError(message || 'Не удалось запустить измерение');
    } finally {
      setLoading(false);
    }
  }, [isReady, state.files]);

  const reset = useCallback(() => {
    setState({
      files: { front: null, side: null, top: null },
      manualRoi: { front: null, side: null, top: null },
    });
    setResult(null);
    setError(null);
  }, []);

  return {
    ...state,
    setFile,
    setRoi,
    clearFile,
    submit,
    reset,
    isReady,
    loading,
    error,
    result,
  };
}