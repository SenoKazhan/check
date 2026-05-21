// frontend/src/app/products/page.tsx
'use client';


import { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';
import { useRouter } from 'next/navigation';

// --- Типы ---
interface Product {
  id: number;
  name: string;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
  qr_code: string | null;
  notes?: string | null;
}

interface ProductFormData {
  name: string;
  qr_code: string;
  ref_length_mm: string;
  ref_width_mm: string;
  ref_height_mm: string;
  notes: string;
}

interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

export default function ProductsPage() {
  const { user } = useAuth();
  const router = useRouter();
  
  // Состояния данных
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Состояния модального окна
  const [showModal, setShowModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formData, setFormData] = useState<ProductFormData>({
    name: '',
    qr_code: '',
    ref_length_mm: '',
    ref_width_mm: '',
    ref_height_mm: '',
    notes: '',
  });
  
  // Состояния формы
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  
  // Состояния для сканирования QR
  const [scanning, setScanning] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!user) {
      router.push('/login');
    }
  }, [user, router]);


  // Загрузка списка товаров
  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const res = await api.get<Product[]>('/api/v1/products/');
      setProducts(res.data);
    } catch {
      setError('Не удалось загрузить товары');
    } finally {
      setLoading(false);
    }
  };

  // Открытие модального окна для создания
  const handleAddClick = () => {
    setEditingProduct(null);
    setFormData({
      name: '',
      qr_code: '',
      ref_length_mm: '',
      ref_width_mm: '',
      ref_height_mm: '',
      notes: '',
    });
    setFormError(null);
    setShowModal(true);
  };

  // Открытие модального окна для редактирования
  const handleEditClick = (product: Product) => {
    setEditingProduct(product);
    setFormData({
      name: product.name,
      qr_code: product.qr_code || '',
      ref_length_mm: product.length_mm?.toString() || '',
      ref_width_mm: product.width_mm?.toString() || '',
      ref_height_mm: product.height_mm?.toString() || '',
      notes: product.notes || '',
    });
    setFormError(null);
    setShowModal(true);
  };

  // Удаление товара
  const handleDeleteClick = async (productId: number, productName: string) => {
    if (!window.confirm(`Удалить товар «${productName}»?`)) return;
    
    try {
      await api.delete(`/api/v1/products/${productId}`);
      setProducts(prev => prev.filter(p => p.id !== productId));
    } catch {
      setError('Не удалось удалить товар');
    }
  };

  // Обработка выбора файла для сканирования QR
  const handleQrFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setScanning(true);
    setFormError(null);
    
    try {
      const formDataScan = new FormData();
      formDataScan.append('file', file);
      
      // Вызов бэкенд-эндпоинта
      const { data } = await api.post('/api/v1/qr/decode', formDataScan, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      
      if (data.qr_string) {
        setFormData(prev => ({ ...prev, qr_code: data.qr_string }));
        setFormError(null);
        
        // Если товар найден — можно автозаполнить поля
        if (data.product) {
          setFormData(prev => ({
            ...prev,
            name: data.product.name || prev.name,
            ref_length_mm: data.product.ref_length_mm?.toString() || prev.ref_length_mm,
            ref_width_mm: data.product.ref_width_mm?.toString() || prev.ref_width_mm,
            ref_height_mm: data.product.ref_height_mm?.toString() || prev.ref_height_mm,
            notes: data.product.notes || prev.notes,
          }));
        }
      } else {
        setFormError('QR-код не обнаружен на изображении');
      }
    } catch (err: unknown) {
      const error = err as ApiErrorResponse;
      setFormError(error.response?.data?.detail || 'Ошибка при сканировании');
    } finally {
      setScanning(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };


  const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setFormError(null);
  setSubmitting(true);

  if (!formData.name.trim()) {
    setFormError('Название обязательно');
    setSubmitting(false);
    return;
  }

  if (formData.name.trim().length < 3) {
    setFormError('Название должно содержать минимум 3 символа');
    setSubmitting(false);
    return;
  }

const lengthNum = formData.ref_length_mm.trim() === '' ? null : parseFloat(formData.ref_length_mm);
if (lengthNum !== null && (isNaN(lengthNum) || lengthNum <= 0)) {
  setFormError('Длина должна быть положительным числом или пустым полем');
  setSubmitting(false);
  return;
}

// Проверка ширины
const widthNum = formData.ref_width_mm.trim() === '' ? null : parseFloat(formData.ref_width_mm);
if (widthNum !== null && (isNaN(widthNum) || widthNum <= 0)) {
  setFormError('Ширина должна быть положительным числом или пустым полем');
  setSubmitting(false);
  return;
}

// Проверка высоты
const heightNum = formData.ref_height_mm.trim() === '' ? null : parseFloat(formData.ref_height_mm);
if (heightNum !== null && (isNaN(heightNum) || heightNum <= 0)) {
  setFormError('Высота должна быть положительным числом или пустым полем');
  setSubmitting(false);
  return;
}

  const payload = {
    name: formData.name.trim(),
    qr_code: formData.qr_code.trim() || null,
    ref_length_mm: lengthNum,
    ref_width_mm: widthNum,
    ref_height_mm: heightNum,
    notes: formData.notes.trim() || null,
  };

  try {
    if (editingProduct) {
      await api.put(`/api/v1/products/${editingProduct.id}`, payload);
    } else {
      await api.post('/api/v1/products/', payload);
    }
    setShowModal(false);
    fetchProducts();
  } catch (err: unknown) {
    const error = err as ApiErrorResponse;
    const detail = error.response?.data?.detail;
    
    // Форматируем ошибку валидации в строку
    if (Array.isArray(detail)) {
      const messages = detail.map((err: any) => {
        const msg = err.msg || err.message || 'Ошибка';
        const field = err.loc?.[1] || err.loc?.[0] || '';
        return field ? `${field}: ${msg}` : msg;
      });
      setFormError(messages.join('; '));
    } else if (typeof detail === 'string') {
      setFormError(detail);
    } else {
      setFormError('Ошибка сохранения товара');
    }
  } finally {
    setSubmitting(false);
  }
};

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Загрузка справочника...</div>;
  }

  if (error) {
    return <div className="p-8 text-center text-red-600">{error}</div>;
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Заголовок + кнопка добавления */}
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-slate-900">Справочник товаров</h1>
          {user?.role === 'admin' && (
            <button
              onClick={handleAddClick}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              + Добавить товар
            </button>
          )}
        </div>
        
        {/* Таблица товаров */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase w-12">ID</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">Наименование</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">Габариты (Д × Ш × В)</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">QR-код</th>
                  {user?.role === 'admin' && (
                    <th className="p-4 text-xs font-semibold text-slate-600 uppercase text-right">Действия</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={user?.role === 'admin' ? 5 : 4} className="p-8 text-center text-slate-400">
                      Справочник пуст. {user?.role === 'admin' && 'Добавьте первый товар.'}
                    </td>
                  </tr>
                ) : (
                  products.map(p => (
                    <tr key={p.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="p-4 text-sm text-slate-500">{p.id}</td>
                      <td className="p-4 text-sm font-medium text-slate-900">{p.name}</td>
                      <td className="p-4 text-sm text-slate-700 font-mono">
                        {p.length_mm ?? '—'} × {p.width_mm ?? '—'} × {p.height_mm ?? '—'} мм
                      </td>
                      <td className="p-4 text-sm text-slate-500">{p.qr_code || '—'}</td>
                      {user?.role === 'admin' && (
                        <td className="p-4 text-right space-x-2">
                          <button
                            onClick={() => handleEditClick(p)}
                            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                          >
                            Изменить
                          </button>
                          <button
                            onClick={() => handleDeleteClick(p.id, p.name)}
                            className="text-sm text-red-600 hover:text-red-800 font-medium"
                          >
                            Удалить
                          </button>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Модальное окно создания/редактирования */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
              {/* Заголовок модального окна */}
              <div className="p-4 border-b border-slate-200 flex justify-between items-center">
                <h3 className="text-lg font-semibold text-slate-900">
                  {editingProduct ? `Редактирование: ${editingProduct.name}` : 'Новый товар'}
                </h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-slate-400 hover:text-slate-600 text-2xl font-bold"
                >
                  ×
                </button>
              </div>

              {/* Форма */}
              <form onSubmit={handleSubmit} className="p-4 space-y-4">
                {formError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                    {formError}
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Наименование *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Например: Коробка 200×150×100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    QR-код
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={formData.qr_code}
                      onChange={e => setFormData({ ...formData, qr_code: e.target.value })}
                      className="flex-1 px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Введите или отсканируйте"
                    />
                    {/* Кнопка сканирования через фото */}
                    <label className="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors cursor-pointer text-sm flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Сканировать
                      {/* Скрытый input для выбора файла */}
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        onChange={handleQrFileSelect}
                        className="hidden"
                        disabled={scanning}
                      />
                    </label>
                  </div>
                  {scanning && (
                    <p className="text-xs text-slate-500 mt-1">Обработка изображения...</p>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Длина, мм
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={formData.ref_length_mm}
                      onChange={e => setFormData({ ...formData, ref_length_mm: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Ширина, мм
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={formData.ref_width_mm}
                      onChange={e => setFormData({ ...formData, ref_width_mm: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Высота, мм
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={formData.ref_height_mm}
                      onChange={e => setFormData({ ...formData, ref_height_mm: e.target.value })}
                      className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="0"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Примечания
                  </label>
                  <textarea
                    value={formData.notes}
                    onChange={e => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Дополнительная информация..."
                  />
                </div>

                {/* Кнопки */}
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    disabled={submitting}
                    className="px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {submitting ? 'Сохранение...' : editingProduct ? 'Обновить' : 'Создать'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}