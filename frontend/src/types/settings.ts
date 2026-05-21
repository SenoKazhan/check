/**
 * Типы для системных настроек.
 * Вынесены в отдельный модуль для повторного использования и типобезопасности.
 */

export type SettingType = 'boolean' | 'number' | 'string';
export type SettingGroupKey = 'computer_vision' | 'verification' | 'uploads' | 'packing';

export interface Setting {
  key: string;
  label: string;
  type: SettingType;
  value: boolean | number | string | null;
  displayValue: string;
  unit: string;
  description: string;
  minValue?: number;
  maxValue?: number;
  step?: number;
}

export interface SettingsGroups {
  computer_vision: Setting[];
  verification: Setting[];
  uploads: Setting[];
  packing: Setting[];
}

export interface SettingsResponse {
  groups: SettingsGroups;
}

export interface SettingUpdateRequest {
  key: string;
  value: boolean | number | string;
}