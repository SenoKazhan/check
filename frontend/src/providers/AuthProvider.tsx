/**
 * Провайдер аутентификации.
 * Работает с httpOnly-куками: не хранит токен в JS, проверяет сессию через /auth/me.
 */
"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export interface User {
  id: number;
  login: string;
  role: "worker" | "admin";
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

  const checkSession = useCallback(async () => {
    try {
      const { data } = await api.get<User>("/auth/me");
      setUser(data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    // Не проверять сессию на странице логина
    if (typeof window !== "undefined" && window.location.pathname === "/login") {
      setLoading(false);
      return;
    }

    let cancelled = false;

    const initAuth = async () => {
      await checkSession();
      if (!cancelled) setLoading(false);
    };

    initAuth();
    return () => { cancelled = true; };
  }, [checkSession]);

  const login = async (login: string, password: string) => {
    try {
      await api.post("/auth/login", { login, password });
      await checkSession();
      // Полная перезагрузка гарантирует отправку куки в следующем запросе
      if (typeof window !== "undefined") {
        window.location.href = "/";
      }
    } catch (err: any) {
      // Fallback: если кука не сработала, пробуем клиентский редирект
      if (typeof window !== "undefined") {
        await checkSession();
        if (user) {
          router.push("/");
        }
      }
      throw err;
    }
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(null);
      router.push("/login");
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
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}