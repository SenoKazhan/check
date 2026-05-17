'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';

export default function LoginPage() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { login: authLogin } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await authLogin(login, password);
      router.replace('/');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const errorResponse = err as { response?: { data?: { detail?: string } } };
        setError(errorResponse.response?.data?.detail || 'Ошибка авторизации');
      } else {
        setError('Не удалось подключиться к серверу');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50 p-4">
      <div className="w-full max-w-md">
        {/* Карточка входа */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">
          {/* Хедер */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-white/20 rounded-lg">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Warehouse CV</h1>
                <p className="text-blue-100 text-sm">Система автоматизированной упаковки</p>
              </div>
            </div>
          </div>

          {/* Форма */}
          <form className="p-6 space-y-5" onSubmit={handleSubmit}>
            {/* Поле логина */}
            <div>
              <label htmlFor="login" className="block text-sm font-medium text-gray-700 mb-1.5">
                Логин
              </label>
              <input
                id="login"
                type="text"
                autoComplete="username"
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500 transition-colors"
                placeholder="admin@warehouse.dev"
                required
                disabled={loading}
              />
            </div>

            {/* Поле пароля */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                Пароль
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-500 transition-colors"
                placeholder="••••••••"
                required
                disabled={loading}
              />
            </div>

            {/* Сообщение об ошибке */}
            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Кнопка входа */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600
                hover:from-blue-700 hover:to-indigo-700
                disabled:from-blue-400 disabled:to-indigo-400
                disabled:cursor-not-allowed text-white font-medium
                rounded-xl transition-all duration-200 shadow-md
                hover:shadow-lg focus:outline-none focus:ring-2
                focus:ring-offset-2 focus:ring-blue-500"
            >
              {loading ? 'Проверка...' : 'Войти в систему'}
            </button>
          </form>

          {/* Футер формы */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-gray-500 text-center">
              Тестовый аккаунт:{' '}
              <code className="bg-gray-200 px-1.5 py-0.5 rounded">admin@warehouse.dev</code> /{' '}
              <code className="bg-gray-200 px-1.5 py-0.5 rounded">admin123</code>
            </p>
          </div>
        </div>

        {/* Подвал страницы */}
        <p className="text-center text-xs text-gray-500 mt-4">
          © 2026 Warehouse CV • Дипломный проект БГУИР
        </p>
      </div>
    </div>
  );
}