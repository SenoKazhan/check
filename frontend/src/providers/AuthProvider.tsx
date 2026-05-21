// frontend/src/providers/AuthProvider.tsx
'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api } from '@/lib/api';

export interface User {
  id: number;
  login: string;
  role: 'worker' | 'admin';
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // Проверка сессии при монтировании
  useEffect(() => {
    let isMounted = true;

    const checkAuth = async () => {
      try {
        const { data } = await api.get<User>('/api/v1/auth/me');
        if (isMounted) {
          setUser(data);
        }
      } catch {
        if (isMounted) {
          setUser(null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    // Не проверяем авторизацию на странице логина
    if (pathname === '/login') {
      setLoading(false);
      return;
    }

    checkAuth();

    return () => {
      isMounted = false;
    };
  }, [pathname]);

  // Вход в систему
  const login = async (login: string, password: string) => {
    try {
      await api.post('/api/v1/auth/login', { login, password });
      const { data } = await api.get<User>('/api/v1/auth/me');
      setUser(data);
      router.push('/');
    } catch (error) {
      throw error;
    }
  };

  // Выход из системы
  const logout = async () => {
    try {
      await api.post('/api/v1/auth/logout');
    } finally {
      setUser(null);
      router.push('/login');
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}