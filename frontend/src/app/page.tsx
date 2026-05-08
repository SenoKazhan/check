'use client';

import { useAuth } from '@/providers/AuthProvider';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Навигация */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <h1 className="text-xl font-bold text-gray-900">Warehouse CV</h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {user.login} <span className="text-gray-400">({user.role})</span>
              </span>
              <button
                onClick={logout}
                className="px-3 py-1.5 text-sm font-medium text-white bg-red-600 rounded hover:bg-red-700 transition-colors"
              >
                Выйти
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Контент */}
      <main className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Добро пожаловать, {user.login}! 
          </h2>
          <p className="text-gray-600">
            Вы успешно авторизовались в системе.
          </p>
          
          <div className="mt-6 pt-6 border-t">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              Статус системы:
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>✅ Срез 1: Авторизация — готов</li>
              <li>⏳ Срез 2: Товары — в разработке</li>
              <li>⏳ Срез 3: CV (бэкенд) — в разработке</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}