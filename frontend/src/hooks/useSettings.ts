/**
 * Хук для управления состоянием настроек.
 * Выносит бизнес-логику из компонента, обеспечивает повторное использование.
 */

import { useState, useCallback } from 'react';
import { SettingsService } from '@/services/settingsService';
import type { SettingsGroups, SettingUpdateRequest } from '@/types/settings';

interface UseSettingsReturn {
  settings: SettingsGroups | null;
  loading: boolean;
  saving: Record<string, boolean>;
  errors: Record<string, string>;
  success: string | null;
  fetchSettings: () => Promise<void>;
  updateSetting: (key: string, value: boolean | number | string, group: keyof SettingsGroups) => Promise<void>;
  resetSetting: (key: string) => Promise<void>;
  updateLocalValue: (group: keyof SettingsGroups, key: string, value: boolean | number | string) => void;
  clearSuccess: () => void;
}

export function useSettings(): UseSettingsReturn {
  const [settings, setSettings] = useState<SettingsGroups | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const data = await SettingsService.fetchAll();
      setSettings(data);
    } catch {
      setErrors({ fetch: 'Не удалось загрузить настройки' });
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSetting = useCallback(
    async (key: string, value: boolean | number | string, group: keyof SettingsGroups) => {
      setSaving((prev) => ({ ...prev, [key]: true }));
      setErrors((prev) => ({ ...prev, [key]: undefined }));
      setSuccess(null);

      try {
        await SettingsService.update(key, { key, value });
        setSuccess(`Настройка "${key}" сохранена`);
        // Обновляем только изменённое значение локально, чтобы избежать race condition
        setSettings((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            [group]: prev[group].map((setting) =>
              setting.key === key
                ? { ...setting, value, displayValue: String(value) }
                : setting
            ),
          };
        });
      } catch (error: unknown) {
        const message =
          error && typeof error === 'object' && 'response' in error
            ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : 'Ошибка сохранения';
        setErrors((prev) => ({ ...prev, [key]: message || 'Ошибка сохранения' }));
      } finally {
        setSaving((prev) => ({ ...prev, [key]: false }));
        setTimeout(() => setSuccess(null), 3000);
      }
    },
    []
  );

  const resetSetting = useCallback(async (key: string) => {
    try {
      await SettingsService.reset(key);
      setSuccess(`Настройка "${key}" сброшена`);
      await fetchSettings();
    } catch {
      setErrors((prev) => ({ ...prev, [key]: 'Ошибка сброса' }));
    }
  }, [fetchSettings]);

  const updateLocalValue = useCallback(
    (group: keyof SettingsGroups, key: string, value: boolean | number | string) => {
      setSettings((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          [group]: prev[group].map((setting) =>
            setting.key === key ? { ...setting, value, displayValue: String(value) } : setting
          ),
        };
      });
      setErrors((prev) => ({ ...prev, [key]: undefined }));
    },
    []
  );

  const clearSuccess = useCallback(() => setSuccess(null), []);

  return {
    settings,
    loading,
    saving,
    errors,
    success,
    fetchSettings,
    updateSetting,
    resetSetting,
    updateLocalValue,
    clearSuccess,
  };
}