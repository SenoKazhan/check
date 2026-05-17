'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';

export default function Navigation() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Левая часть: Логотип + Ссылки */}
          <div className="flex items-center gap-6">
            <Link href="/" className="text-xl font-bold text-blue-600">
              📦 Warehouse CV
            </Link>

            <div className="hidden md:flex items-center gap-1">
              <Link
                href="/measure"
                className={`px-3 py-2 rounded-lg text-sm font-medium ${
                  pathname === '/measure'
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                📏 Измерение
              </Link>

              <Link
                href="/products"
                className={`px-3 py-2 rounded-lg text-sm font-medium ${
                  pathname === '/products'
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                📦 Товары
              </Link>

              {user.role === 'admin' && (
                <Link
                  href="/settings"
                  className={`px-3 py-2 rounded-lg text-sm font-medium ${
                    pathname === '/settings'
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  ⚙️ Настройки
                </Link>
              )}
            </div>
          </div>

          {/* Правая часть: Пользователь + Выход */}
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-600">
              {user.login} 
              <span className="ml-2 px-2 py-0.5 bg-gray-100 rounded text-xs">
                {user.role === 'admin' ? 'Админ' : 'Оператор'}
              </span>
            </div>
            <button
              onClick={logout}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}