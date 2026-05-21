// frontend/src/types/index.ts
export interface User {
  id: number;
  login: string;
  role: 'worker' | 'admin';
}

export interface MeasurementResult {
  measurement_id: number;
  dimensions_mm: { length_mm: number; width_mm: number; height_mm: number };
  confidence: number;
  final_status: 'completed' | 'needs_review' | 'failed';
  verified_ok?: boolean;
  delta_pct?: number;
}

export interface Placement {
  item_id: number;
  x_mm: number; y_mm: number; z_mm: number;
  length_mm: number; width_mm: number; height_mm: number;
  rotated: boolean;
}

export interface PackResult {
  box_l_mm: number; box_w_mm: number; box_h_mm: number;
  box_volume_cm3: number;
  placements: Placement[];
  variant_index: number;
}