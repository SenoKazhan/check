'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/providers/AuthProvider';
import { api } from '@/lib/api';
import { useRouter } from 'next/navigation';

// Типы для настроек
interface Setting {
  key: string;
  label: string;
  type: 'boolean' | 'number' | 'string';
  value: any;
  display_value: any;
  unit: string;
  description: string;
  min?: number;
  max?: number;
  step?: number;
}

interface SettingsGroups {
  computer_vision: Setting[];
  verification: Setting[];
  uploads: Setting[];
  packing: Setting[];
}

interface SettingsResponse {
  groups: SettingsGroups;
}

// Группы настроек с иконками и названиями
const GROUP_CONFIG: Record<keyof SettingsGroups, { title: string; icon: string }> = {
  computer_vision: { title: 'Компьютерное зрение', icon: '🔍' },
  verification: { title: 'Верификация', icon: '✅' },
  uploads: { title: 'Загрузка файлов', icon: '📤' },
  packing: { title: 'Упаковка', icon: '📦' },
};

export default function SettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  
  const [settings, setSettings] = useState<SettingsGroups | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<keyof SettingsGroups>('computer_vision');

  // Защита от не-админов
  useEffect(() => {
    if (!authLoading && (!user || user.role !== 'admin')) {
      router.push('/');
    }
  }, [user, authLoading, router]);

  // Загрузка настроек
  const fetchSettings = async () => {
    try {
      const { data } = await api.get<SettingsResponse>('/api/v1/settings/');
      setSettings(data.groups);
    } catch (err) {
      setErrors({ fetch: 'Не удалось загрузить настройки' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSettings(); }, []);

  // Обработчик изменения значения
  const handleChange = (group: keyof SettingsGroups, key: string, value: any) => {
    setSettings(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [group]: prev[group].map(s => 
          s.key === key ? { ...s, value, display_value: value } : s
        ),
      };
    });
    setErrors(prev => ({ ...prev, [key]: undefined }));
  };

  // Сохранение настройки
  const handleSave = async (key: string, value: any, group: keyof SettingsGroups) => {
    setSaving(prev => ({ ...prev, [key]: true }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
    setSuccess(null);

    try {
      await api.patch(`/api/v1/settings/${key}`, { value });
      setSuccess(`Настройка "${key}" сохранена`);
      // Обновляем локально
      fetchSettings();
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Ошибка сохранения';
      setErrors(prev => ({ ...prev, [key]: msg }));
    } finally {
      setSaving(prev => ({ ...prev, [key]: false }));
      setTimeout(() => setSuccess(null), 3000);
    }
  };

  // Сброс к дефолту
  const handleReset = async (key: string) => {
    if (!confirm('Сбросить настройку к значению по умолчанию?')) return;
    
    try {
      await api.delete(`/api/v1/settings/${key}`);
      setSuccess(`Настройка "${key}" сброшена`);
      fetchSettings();
    } catch {
      setErrors(prev => ({ ...prev, [key]: 'Ошибка сброса' }));
    }
  };

  // Рендер поля ввода в зависимости от типа
  const renderInput = (setting: Setting, group: keyof SettingsGroups) => {
    const { key, type, value, unit, min, max, step } = setting;
    const error = errors[key];
    const isSaving = saving[key];

    switch (type) {
      case 'boolean':
        return (
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={!!value}
              onChange={e => handleChange(group, key, e.target.checked)}
              className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              disabled={isSaving}
            />
            <span className="text-sm text-gray-600">{value ? 'Включено' : 'Отключено'}</span>
          </label>
        );

      case 'number':
        return (
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={value ?? ''}
              onChange={e => {
                const num = e.target.value === '' ? null : parseFloat(e.target.value);
                handleChange(group, key, num);
              }}
              min={min}
              max={max}
              step={step}
              className={`w-32 px-3 py-2 border rounded-lg text-right ${
                error ? 'border-red-300' : 'border-gray-300'
              } focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
              disabled={isSaving}
            />
            {unit && <span className="text-sm text-gray-500">{unit}</span>}
          </div>
        );

      case 'string':
      default:
        return (
          <input
            type="text"
            value={value ?? ''}
            onChange={e => handleChange(group, key, e.target.value)}
            className={`w-full px-3 py-2 border rounded-lg ${
              error ? 'border-red-300' : 'border-gray-300'
            } focus:ring-2 focus:ring-blue-500 focus:border-blue-500`}
            disabled={isSaving}
          />
        );
    }
  };

  if (authLoading || loading) {
    return (
      <div className="p-8 text-center text-gray-500">
        Загрузка настроек...
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
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">⚙️ Настройки системы</h1>
        {success && (
          <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
            {success}
          </span>
        )}
      </div>

      {/* Табы групп */}
      <div className="flex gap-2 mb-6 border-b">
        {(Object.keys(GROUP_CONFIG) as Array<keyof SettingsGroups>).map(group => (
          <button
            key={group}
            onClick={() => setActiveTab(group)}
            className={`px-4 py-2 rounded-t-lg font-medium transition ${
              activeTab === group
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {GROUP_CONFIG[group].icon} {GROUP_CONFIG[group].title}
          </button>
        ))}
      </div>

      {/* Список настроек активной группы */}
      <div className="space-y-4">
        {settings[activeTab].map(setting => (
          <div key={setting.key} className="bg-white rounded-xl p-4 shadow border border-gray-100">
            <div className="flex justify-between items-start gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-gray-900">{setting.label}</h3>
                  <span className="text-xs text-gray-400 font-mono">{setting.key}</span>
                </div>
                <p className="text-sm text-gray-500 mb-3">{setting.description}</p>
                
                {/* Поле ввода + кнопки */}
                <div className="flex items-center gap-3">
                  {renderInput(setting, activeTab)}
                  
                  <button
                    onClick={() => handleSave(setting.key, setting.value, activeTab)}
                    disabled={saving[setting.key]}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition text-sm"
                  >
                    {saving[setting.key] ? 'Сохранение...' : 'Сохранить'}
                  </button>
                  
                  <button
                    onClick={() => handleReset(setting.key)}
                    className="px-3 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition text-sm"
                    title="Сбросить к значению по умолчанию"
                  >
                    ↺ Сброс
                  </button>
                </div>
                
                {errors[setting.key] && (
                  <p className="mt-2 text-sm text-red-600">{errors[setting.key]}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Подсказка для пользователя */}
      <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <strong>💡 Подсказка:</strong> Изменения применяются немедленно. 
        Некоторые параметры (например, лимиты загрузки) требуют перезагрузки страницы для вступления в силу.
      </div>
    </div>
  );
}