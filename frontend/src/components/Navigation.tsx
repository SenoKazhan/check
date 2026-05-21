// frontend/src/components/Navigation.tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/providers/AuthProvider';
import { IconRuler, IconBox, IconCog, IconUsers } from './Icons';

export default function Navigation() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) return null;

  // Ссылки, доступные всем (включая worker)
  const commonLinks = [
    { href: '/measure', label: 'Измерение', Icon: IconRuler },
    { href: '/packing', label: 'Упаковка', Icon: IconBox },
    { href: '/products', label: 'Товары', Icon: IconBox },
  ];

  // Ссылки только для администратора
  const adminLinks = [
    { href: '/users', label: 'Пользователи', Icon: IconUsers },
    { href: '/settings', label: 'Настройки', Icon: IconCog },
  ];

  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-xl font-bold text-blue-600 flex items-center gap-2">
              <IconBox /> Warehouse CV
            </Link>
            <div className="hidden md:flex items-center gap-1">
              {commonLinks.map(({ href, label, Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    pathname === href ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon /> {label}
                </Link>
              ))}
              {user.role === 'admin' && adminLinks.map(({ href, label, Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    pathname === href ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon /> {label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-600">
              {user.login}
              <span className="ml-2 px-2 py-0.5 bg-gray-100 rounded text-xs uppercase">
                {user.role}
              </span>
            </div>
            <button onClick={logout} className="text-sm text-red-600 hover:text-red-700 font-medium">
              Выход
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}