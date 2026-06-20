// frontend/src/hooks/useImageUpload.ts
import { useState, useCallback, useEffect, useRef } from 'react';
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
    
    // Ref для хранения интервала поллинга
    const intervalRef = useRef<NodeJS.Timeout | null>(null);

    const isReady = Object.values(state.files).every((file) => file !== null);

    useEffect(() => {
        return () => {
            Object.values(state.files).forEach((file) => {
                if (file) URL.revokeObjectURL(URL.createObjectURL(file));
            });
            // Очищаем интервал при размонтировании
            if (intervalRef.current) clearInterval(intervalRef.current);
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

            // 1. Отправляем файлы и получаем task_id
            const { data } = await api.post('/api/v1/measurements/start', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            const taskId = data.task_id;

            // 2. Запускаем поллинг статуса задачи Celery каждые 2 секунды
            intervalRef.current = setInterval(async () => {
                try {
                    const taskRes = await api.get(`/api/v1/tasks/${taskId}`);
                    const taskData = taskRes.data;

                    if (taskData.state === 'SUCCESS') {
                        if (intervalRef.current) clearInterval(intervalRef.current);
                        setLoading(false);
                        
                        // Маппинг snake_case (от бэкенда) в camelCase (для типов фронтенда)
                        const backendResult = taskData.result;
                        setResult({
                            status: backendResult.status,
                            measurementId: backendResult.measurement_id,
                            finalStatus: backendResult.final_status,
                            confidence: backendResult.confidence,
                            dimensions_mm: backendResult.dimensions_mm,
                        });
                    } else if (taskData.state === 'FAILURE') {
                        if (intervalRef.current) clearInterval(intervalRef.current);
                        setLoading(false);
                        setError(taskData.error || 'Ошибка обработки измерения на сервере');
                    }
                } catch (pollErr) {
                    if (intervalRef.current) clearInterval(intervalRef.current);
                    setLoading(false);
                    setError('Ошибка опроса статуса задачи');
                }
            }, 2000); 

        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Ошибка сети или сервера';
            setError(message || 'Не удалось запустить измерение');
            setLoading(false);
        }
    }, [isReady, state.files]);

    const reset = useCallback(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
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