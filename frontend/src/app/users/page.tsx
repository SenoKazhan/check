// frontend/src/app/users/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { UserService } from '@/services/userService';
import { User } from '@/types';
import { IconUsers } from '@/components/Icons';

export default function UsersAdministrationPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [isEditing, setIsEditing] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [formState, setFormState] = useState({ login: '', password: '', role: 'worker' });

  const fetchUsers = useCallback(async () => {
    try {
      const data = await UserService.fetchUsers();
      setUsers(data);
    } catch {
      setError('Не удалось загрузить пользователей');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      if (isEditing && editingUser) {
        const payload: any = { login: formState.login, role: formState.role };
        if (formState.password) payload.password = formState.password;
        await UserService.updateUser(editingUser.id, payload);
      } else {
        if (!formState.password) { setError('Требуется пароль'); return; }
        await UserService.createUser(formState);
      }
      resetForm();
      fetchUsers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Ошибка операции');
    }
  };

  const handleEdit = (user: User) => {
    setIsEditing(true);
    setEditingUser(user);
    setFormState({ login: user.login, password: '', role: user.role });
  };

  const handleDelete = async (userId: number, login: string) => {
    if (!window.confirm(`Удалить пользователя «${login}»?`)) return;
    try {
      await UserService.deleteUser(userId);
      fetchUsers();
    } catch {
      setError('Ошибка удаления');
    }
  };

  const resetForm = () => {
    setIsEditing(false);
    setEditingUser(null);
    setFormState({ login: '', password: '', role: 'worker' });
  };

  return (
    <div className="p-6 max-w-5xl mx-auto bg-white rounded-xl shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
          <IconUsers /> Управление пользователями
        </h2>
      </div>

      {/* Форма создания/редактирования */}
      <form onSubmit={handleFormSubmit} className="mb-8 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <h3 className="text-lg font-semibold mb-4 text-gray-800">
          {isEditing ? `Редактирование: ${editingUser?.login}` : 'Новый пользователь'}
        </h3>
        {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded border border-red-200 text-sm">{error}</div>}
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Логин</label>
            <input type="text" required value={formState.login} onChange={e => setFormState({...formState, login: e.target.value})} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Пароль {isEditing && <span className="text-xs text-gray-400">(оставьте пустым)</span>}
            </label>
            <input type="password" required={!isEditing} value={formState.password} onChange={e => setFormState({...formState, password: e.target.value})} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Роль</label>
            <select value={formState.role} onChange={e => setFormState({...formState, role: e.target.value})} className="w-full px-3 py-2 border border-gray-300 bg-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="worker">Оператор</option>
              <option value="admin">Администратор</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
              {isEditing ? 'Обновить' : 'Создать'}
            </button>
            {isEditing && (
              <button type="button" onClick={resetForm} className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-sm">
                Отмена
              </button>
            )}
          </div>
        </div>
      </form>

      {/* Таблица пользователей */}
      {loading ? <p className="text-gray-500 text-center py-4">Загрузка...</p> : (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="p-3 text-xs font-semibold text-gray-600 uppercase">ID</th>
                <th className="p-3 text-xs font-semibold text-gray-600 uppercase">Логин</th>
                <th className="p-3 text-xs font-semibold text-gray-600 uppercase">Роль</th>
                <th className="p-3 text-xs font-semibold text-gray-600 uppercase text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                  <td className="p-3 text-sm text-gray-500">{u.id}</td>
                  <td className="p-3 text-sm font-medium text-gray-900">{u.login}</td>
                  <td className="p-3">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${u.role === 'admin' ? 'bg-purple-50 text-purple-700' : 'bg-blue-50 text-blue-700'}`}>
                      {u.role === 'admin' ? 'Админ' : 'Оператор'}
                    </span>
                  </td>
                  <td className="p-3 text-right space-x-4">
                    <button onClick={() => handleEdit(u)} className="text-sm text-blue-600 hover:text-blue-800 font-medium">Изменить</button>
                    <button onClick={() => handleDelete(u.id, u.login)} className="text-sm text-red-600 hover:text-red-800 font-medium">Удалить</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}