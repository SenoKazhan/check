/**
 * Сервис для работы с системными настройками.
 * Инкапсулирует логику взаимодействия с API, соответствует принципу единственной ответственности.
 */

import { api } from '@/lib/api';
import type { SettingsGroups, SettingUpdateRequest } from '@/types/settings';

export class SettingsService {
  private static readonly BASE_PATH = '/api/v1/settings';

  /**
   * Получает все настройки, сгруппированные по категориям.
   */
  static async fetchAll(): Promise<SettingsGroups> {
    const { data } = await api.get<{ groups: SettingsGroups }>(this.BASE_PATH);
    return data.groups;
  }

  /**
   * Обновляет значение конкретной настройки.
   */
  static async update(key: string, payload: SettingUpdateRequest): Promise<void> {
    await api.patch(`${this.BASE_PATH}/${key}`, payload);
  }

  /**
   * Сбрасывает настройку к значению по умолчанию.
   */
  static async reset(key: string): Promise<void> {
    await api.delete(`${this.BASE_PATH}/${key}`);
  }
}