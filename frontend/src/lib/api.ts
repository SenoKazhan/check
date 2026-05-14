/**
 * Axios-инстанс для API-запросов.
 * Автоматически отправляет/принимает httpOnly-куки.
 */
import axios from 'axios';

export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  withCredentials: true,  
  headers: {
    "Content-Type": "application/json",
  },
});

// Обработка ответов: 401 → редирект на логин
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      // Токен истёк или невалиден → очистить сессию
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);