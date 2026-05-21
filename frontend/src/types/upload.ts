/**
 * Типы для модуля загрузки и измерения.
 */

export type ViewAngle = 'front' | 'side' | 'top';

export interface MeasurementDimensions {
  length_mm?: number;
  width_mm?: number;
  height_mm?: number;
}

export interface MeasurementResult {
  status: string;
  measurementId: number;
  finalStatus: string;
  confidence: number;
  dimensions_mm: MeasurementDimensions;
}

export interface UploadState {
  files: Record<ViewAngle, File | null>;
  manualRoi: Record<ViewAngle, string | null>;
}