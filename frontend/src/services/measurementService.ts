// frontend/src/services/measurementService.ts
import { apiClient } from './apiClient';

export class MeasurementService {
  static async startMeasurement(formData: FormData, manualRoi?: string | null) {
    const response = await apiClient.post("/api/v1/measurements/start", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      params: { manual_roi: manualRoi || undefined },
    });
    return response.data;
  }

  static async getTaskStatus(taskId: string) {
    const response = await apiClient.get(`/api/v1/tasks/${taskId}`);
    return response.data;
  }
}