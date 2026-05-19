"use client";
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface User {
  id: number;
  login: string;
  role: string;
  created_at: string;
}

interface ApiErrorResponse {
  detail?: string;
}

export default function UsersAdminPanel() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('worker');
  
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Загрузка списка пользователей – обёрнута в useCallback для стабильности
  const fetchUsers = useCallback(async () => {
    try {
      const res = await axios.get<{ users: User[] }>(`${API_URL}/api/v1/users/`, { withCredentials: true });
      setUsers(res.data.users);
    } catch {
      setError('Не удалось загрузить пользователей');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const resetForm = () => {
    setLogin('');
    setPassword('');
    setRole('worker');
    setEditingUser(null);
    setShowForm(false);
    setError('');
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setLogin(user.login);
    setRole(user.role);
    setPassword('');
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!editingUser && password.length < 6) {
      setError('Пароль должен содержать минимум 6 символов');
      return;
    }

    try {
      const payload: { login: string; role: string; password?: string } = { login, role };
      if (password) payload.password = password;

      if (editingUser) {
        await axios.put(`${API_URL}/api/v1/users/${editingUser.id}`, payload, { withCredentials: true });
        setSuccess(`Пользователь «${login}» обновлен`);
      } else {
        if (!password) { setError('Введите пароль'); return; }
        await axios.post(`${API_URL}/api/v1/users/`, { login, password, role }, { withCredentials: true });
        setSuccess(`Пользователь «${login}» создан`);
      }
      resetForm();
      fetchUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: unknown) {
      const errorResponse = err as { response?: { data?: ApiErrorResponse } };
      setError(errorResponse.response?.data?.detail || 'Ошибка операции');
    }
  };

  const handleDelete = async (userId: number, userLogin: string) => {
    if (!window.confirm(`Вы уверены, что хотите удалить пользователя «${userLogin}»?`)) return;
    
    try {
      await axios.delete(`${API_URL}/api/v1/users/${userId}`, { withCredentials: true });
      setSuccess(`Пользователь «${userLogin}» удален`);
      fetchUsers();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: unknown) {
      const errorResponse = err as { response?: { data?: ApiErrorResponse } };
      setError(errorResponse.response?.data?.detail || 'Ошибка удаления');
    }
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Управление пользователями</h2>
        {!showForm && (
          <button 
            onClick={() => { resetForm(); setShowForm(true); }}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            + Добавить пользователя
          </button>
        )}
      </div>

      {error && <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">{error}</div>}
      {success && <div className="mb-4 p-3 bg-green-100 text-green-700 rounded">{success}</div>}

      {showForm && (
        <div className="mb-6 p-4 border rounded-lg bg-gray-50">
          <h3 className="text-lg font-semibold mb-3">
            {editingUser ? `Редактирование: ${editingUser.login}` : 'Новый пользователь'}
          </h3>
          <form onSubmit={handleSubmit} className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[150px]">
              <label className="block text-sm font-medium text-gray-700">Логин</label>
              <input
                type="text"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                required
                className="mt-1 block w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div className="flex-1 min-w-[150px]">
              <label className="block text-sm font-medium text-gray-700">
                Пароль {editingUser && <span className="text-xs text-gray-400">(оставьте пустым, чтобы не менять)</span>}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required={!editingUser}
                className="mt-1 block w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div className="w-[150px]">
              <label className="block text-sm font-medium text-gray-700">Роль</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border bg-white rounded-md"
              >
                <option value="worker">Оператор</option>
                <option value="admin">Администратор</option>
              </select>
            </div>
            <div className="flex gap-2">
              <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                {editingUser ? 'Сохранить' : 'Создать'}
              </button>
              <button type="button" onClick={resetForm} className="px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400">
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {loading ? <p>Загрузка...</p> : (
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100 border-b">
              <th className="p-3">ID</th>
              <th className="p-3">Логин</th>
              <th className="p-3">Роль</th>
              <th className="p-3">Действия</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b hover:bg-gray-50">
                <td className="p-3">{u.id}</td>
                <td className="p-3 font-medium">{u.login}</td>
                <td className="p-3">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${u.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'}`}>
                    {u.role === 'admin' ? 'Админ' : 'Оператор'}
                  </span>
                </td>
                <td className="p-3 flex gap-2">
                  <button onClick={() => handleEdit(u)} className="text-sm text-blue-600 hover:underline">Изменить</button>
                  <button onClick={() => handleDelete(u.id, u.login)} className="text-sm text-red-600 hover:underline">Удалить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}