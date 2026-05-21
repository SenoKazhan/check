'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';
import { useSettings } from '@/hooks/useSettings';
import type { SettingGroupKey, SettingsGroups } from '@/types/settings';

// Конфигурация групп настроек (только данные, без логики)
const GROUP_CONFIG: Record<SettingGroupKey, { title: string; icon: string }> = {
  computer_vision: { title: 'Компьютерное зрение', icon: '🔍' },
  verification: { title: 'Верификация', icon: '✅' },
  uploads: { title: 'Загрузка файлов', icon: '📤' },
  packing: { title: 'Упаковка', icon: '📦' },
};

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const {
    settings,
    loading,
    saving,
    errors,
    success,
    fetchSettings,
    updateSetting,
    resetSetting,
    updateLocalValue,
  } = useSettings();

  // Защита маршрута: доступ только для администраторов
  useEffect(() => {
    if (!authLoading && (!user || user.role !== 'admin')) {
      router.replace('/');
    }
  }, [user, authLoading, router]);

  // Инициализация: загрузка настроек при монтировании
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-gray-600">Загрузка настроек...</p>
        </div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="p-8 text-center text-red-600">
        {errors.fetch || 'Ошибка загрузки настроек'}
      </div>
    );
  }

  return (
    <SettingsContent
      settings={settings}
      saving={saving}
      errors={errors}
      success={success}
      onUpdate={updateSetting}
      onReset={resetSetting}
      onLocalChange={updateLocalValue}
    />
  );
}

/**
 * Компонент отображения контента настроек.
 * Вынесен в отдельную функцию для соблюдения принципа единственной ответственности.
 */
function SettingsContent({
  settings,
  saving,
  errors,
  success,
  onUpdate,
  onReset,
  onLocalChange,
}: {
  settings: SettingsGroups;
  saving: Record<string, boolean>;
  errors: Record<string, string>;
  success: string | null;
  onUpdate: (key: string, value: boolean | number | string, group: SettingGroupKey) => Promise<void>;
  onReset: (key: string) => Promise<void>;
  onLocalChange: (group: SettingGroupKey, key: string, value: boolean | number | string) => void;
}) {
  const [activeTab, setActiveTab] = useState<SettingGroupKey>('computer_vision');

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Настройки системы</h1>
        {success && (
          <span className="rounded-full bg-green-100 px-3 py-1 text-sm text-green-700">
            {success}
          </span>
        )}
      </div>

      {/* Навигация по группам настроек */}
      <TabNavigation
        activeTab={activeTab}
        onTabChange={setActiveTab}
        groups={GROUP_CONFIG}
      />

      {/* Список настроек активной группы */}
      <div className="space-y-4">
        {settings[activeTab].map((setting) => (
          <SettingCard
            key={setting.key}
            setting={setting}
            group={activeTab}
            isSaving={!!saving[setting.key]}
            error={errors[setting.key]}
            onChange={onLocalChange}
            onSave={onUpdate}
            onReset={onReset}
          />
        ))}
      </div>

      {/* Информационная подсказка */}
      <InfoBanner />
    </div>
  );
}

/**
 * Компонент навигации по вкладкам настроек.
 */
function TabNavigation({
  activeTab,
  onTabChange,
  groups,
}: {
  activeTab: SettingGroupKey;
  onTabChange: (tab: SettingGroupKey) => void;
  groups: Record<SettingGroupKey, { title: string; icon: string }>;
}) {
  return (
    <div className="mb-6 flex gap-2 border-b">
      {(Object.keys(groups) as SettingGroupKey[]).map((group) => (
        <button
          key={group}
          onClick={() => onTabChange(group)}
          className={`rounded-t-lg px-4 py-2 text-sm font-medium transition ${
            activeTab === group
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {groups[group].icon} {groups[group].title}
        </button>
      ))}
    </div>
  );
}

/**
 * Компонент карточки отдельной настройки.
 */
function SettingCard({
  setting,
  group,
  isSaving,
  error,
  onChange,
  onSave,
  onReset,
}: {
  setting: import('@/types/settings').Setting;
  group: SettingGroupKey;
  isSaving: boolean;
  error?: string;
  onChange: (group: SettingGroupKey, key: string, value: boolean | number | string) => void;
  onSave: (key: string, value: boolean | number | string, group: SettingGroupKey) => Promise<void>;
  onReset: (key: string) => Promise<void>;
}) {
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{setting.label}</h3>
            <span className="font-mono text-xs text-gray-400">{setting.key}</span>
          </div>
          <p className="mb-3 text-sm text-gray-500">{setting.description}</p>

          <div className="flex items-center gap-3">
            <SettingInput
              setting={setting}
              group={group}
              disabled={isSaving}
              error={!!error}
              onChange={onChange}
            />

            <button
              onClick={() => onSave(setting.key, setting.value, group)}
              disabled={isSaving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSaving ? 'Сохранение...' : 'Сохранить'}
            </button>

            <button
              onClick={() => onReset(setting.key)}
              className="rounded-lg px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
              title="Сбросить к значению по умолчанию"
            >
              ↺ Сброс
            </button>
          </div>

          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  );
}

/**
 * Компонент ввода значения настройки в зависимости от типа.
 */
function SettingInput({
  setting,
  group,
  disabled,
  error,
  onChange,
}: {
  setting: import('@/types/settings').Setting;
  group: SettingGroupKey;
  disabled: boolean;
  error: boolean;
  onChange: (group: SettingGroupKey, key: string, value: boolean | number | string) => void;
}) {
  const { key, type, value, unit, minValue, maxValue, step } = setting;

  if (type === 'boolean') {
    return (
      <label className="flex cursor-pointer items-center gap-3">
        <input
          type="checkbox"
          checked={!!value}
          onChange={(e) => onChange(group, key, e.target.checked)}
          disabled={disabled}
          className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm text-gray-600">{value ? 'Включено' : 'Отключено'}</span>
      </label>
    );
  }

  if (type === 'number') {
    return (
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value ?? ''}
          onChange={(e) => {
            const num = e.target.value === '' ? null : parseFloat(e.target.value);
            if (num !== null) onChange(group, key, num);
          }}
          min={minValue}
          max={maxValue}
          step={step}
          disabled={disabled}
          className={`w-32 rounded-lg border px-3 py-2 text-right focus:border-blue-500 focus:ring-2 focus:ring-blue-500 ${
            error ? 'border-red-300' : 'border-gray-300'
          }`}
        />
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
    );
  }

  return (
    <input
      type="text"
      value={value ?? ''}
      onChange={(e) => onChange(group, key, e.target.value)}
      disabled={disabled}
      className={`w-full rounded-lg border px-3 py-2 focus:border-blue-500 focus:ring-2 focus:ring-blue-500 ${
        error ? 'border-red-300' : 'border-gray-300'
      }`}
    />
  );
}

/**
 * Информационный баннер с подсказкой.
 */
function InfoBanner() {
  return (
    <div className="mt-8 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
      <strong>Подсказка:</strong> Изменения применяются немедленно. Некоторые параметры
      (например, лимиты загрузки) требуют перезагрузки страницы для вступления в силу.
    </div>
  );
}