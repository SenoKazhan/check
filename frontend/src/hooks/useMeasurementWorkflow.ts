// frontend/src/hooks/useMeasurementWorkflow.ts
import { useState, useEffect, useCallback } from 'react';
import { MeasurementService } from '@/services/measurementService';
import { MeasurementResult } from '@/types';

type View = 'front' | 'side' | 'top';

export function useMeasurementWorkflow() {
  const [files, setFiles] = useState<Record<View, File | null>>({ front: null, side: null, top: null });
  const [manualRoi, setManualRoi] = useState<Record<View, string | null>>({ front: null, side: null, top: null });
  
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<string>('');
  const [result, setResult] = useState<MeasurementResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollTaskStatus = useCallback(async (id: string) => {
    try {
      const data = await MeasurementService.getTaskStatus(id);
      setTaskState(data.state);
      if (data.state === 'SUCCESS') {
        setResult(data.result);
        setLoading(false);
      } else if (data.state === 'FAILURE') {
        setError(data.error || 'Processing failed');
        setLoading(false);
      }
    } catch {
      setError('Failed to fetch task status');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!taskId || taskState === 'SUCCESS' || taskState === 'FAILURE') return;
    const interval = setInterval(() => pollTaskStatus(taskId), 2000);
    return () => clearInterval(interval);
  }, [taskId, taskState, pollTaskStatus]);

  const submitMeasurement = async () => {
    if (!files.front || !files.side || !files.top) {
      setError('All 3 images are required');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('files', files.front);
    formData.append('files', files.side);
    formData.append('files', files.top);

    try {
      const data = await MeasurementService.startMeasurement(formData, manualRoi.front);
      setTaskId(data.task_id);
      setTaskState('PENDING');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
      setLoading(false);
    }
  };

  const setFile = (view: View, file: File | null) => {
    setFiles(prev => ({ ...prev, [view]: file }));
  };

  const setRoi = (view: View, roi: string | null) => {
    setManualRoi(prev => ({ ...prev, [view]: roi }));
  };

  return { files, manualRoi, loading, taskState, result, error, setFile, setRoi, submitMeasurement };
}