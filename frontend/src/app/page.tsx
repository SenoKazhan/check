'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-500">Загрузка...</div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation уже есть в layout.tsx, не нужно добавлять его снова */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Добро пожаловать, {user.login}!
          </h1>
          <p className="mt-2 text-gray-600">
            Система автоматизированного измерения и упаковки товаров
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div 
            onClick={() => router.push('/measure')}
            className="bg-white p-6 rounded-xl shadow-md border border-gray-200 cursor-pointer hover:shadow-lg transition hover:border-blue-400"
          >
            <div className="text-4xl mb-4">📏</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Измерение габаритов
            </h2>
            <p className="text-gray-600 text-sm">
              Загрузите фотографии товара с трёх ракурсов для автоматического определения размеров
            </p>
          </div>

          <div 
            onClick={() => router.push('/products')}
            className="bg-white p-6 rounded-xl shadow-md border border-gray-200 cursor-pointer hover:shadow-lg transition hover:border-blue-400"
          >
            <div className="text-4xl mb-4">📦</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Справочник товаров
            </h2>
            <p className="text-gray-600 text-sm">
              Просмотр и управление товарами с эталонными габаритами
            </p>
          </div>

          {user.role === 'admin' && (
            <div 
              onClick={() => router.push('/settings')}
              className="bg-white p-6 rounded-xl shadow-md border border-gray-200 cursor-pointer hover:shadow-lg transition hover:border-blue-400"
            >
              <div className="text-4xl mb-4">⚙️</div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Настройки системы
              </h2>
              <p className="text-gray-600 text-sm">
                Управление параметрами системы и пользователями
              </p>
            </div>
          )}
        </div>

        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            📋 Как работать с системой:
          </h3>
          <ol className="list-decimal list-inside space-y-2 text-blue-800 text-sm">
            <li>Отсканируйте QR-код товара или загрузите фотографии</li>
            <li>Система автоматически определит габариты</li>
            <li>Добавьте товар в сеанс упаковки</li>
            <li>Получите оптимальную схему укладки</li>
          </ol>
        </div>
      </main>
    </div>
  );
}