'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export interface User {
  id: number;
  login: string;
  role: 'admin' | 'worker';
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Проверка сессии при монтировании провайдера
  useEffect(() => {
    checkSession();
  }, []);

  const login = async (loginValue: string, passwordValue: string) => {
  try {
    // Отправляем JSON, как ожидает LoginRequest
    await api.post('/auth/login', {
      login: loginValue,      // ← поле 'login', не 'username'
      password: passwordValue
    });
    
    await checkSession();
    if (user) {
      router.push('/');
    }
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'response' in err) {
      const error = err as { response?: { status?: number; data?: { detail?: string } } };
      if (error.response?.status === 401) {
        throw new Error('Неверный логин или пароль');
      }
    }
    throw err;
  }
};

  const logout = async () => {
    try {
      await api.post('/auth/logout');  // ← Тоже без /api
    } catch {
      // Игнорируем ошибки
    } finally {
      setUser(null);
      router.push('/login');
    }
  };

  const checkSession = async () => {
    try {
      const { data } = await api.get<User>('/auth/me');  // ← Тоже без /api
      setUser(data);
    } catch {
      setUser(null);
    }
  };

    const value: AuthContextType = {
      user,
      loading,
      login,
      logout,
      checkSession
    };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// Хук для использования контекста
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}