// frontend/src/app/packing/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import PackVisualizer, { PackResult } from '@/components/PackVisualizer';
import { useAuth } from '@/providers/AuthProvider';
import { useRouter } from 'next/navigation';
import { hasPermission, Permission } from '@/lib/permissions';

// Интерфейсы для типизации
interface Product {
  id: number;
  name: string;
  length_mm: number;
  width_mm: number;
  height_mm: number;
}

// Интерфейс для "сырых" данных с бэкенда (могут отличаться названиями полей или наличием null)
interface RawProductResponse {
  id: number;
  name?: string | null;
  ref_length_mm?: number | null; // Бэкенд может отдавать как ref_length_mm
  ref_width_mm?: number | null;
  ref_height_mm?: number | null;
  length_mm?: number | null;     // Или просто length_mm
  width_mm?: number | null;
  height_mm?: number | null;
}

interface CartItem {
  product: Product;
  quantity: number;
}

interface ApiErrorResponse {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

export default function PackingPage() {
  const { user } = useAuth();
  const router = useRouter();
  
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [packResults, setPackResults] = useState<PackResult[] | null>(null);
  const [selectedVariant, setSelectedVariant] = useState(0);

  useEffect(() => {
    if (user && !hasPermission(user.role, Permission.EXECUTE_PACKING)) {
      router.push('/');
    }
  }, [user, router]);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      // ИСПРАВЛЕНО: Используем RawProductResponse вместо any
      const res = await api.get<RawProductResponse[]>('/api/v1/products/');
      
      const fetchedProducts = (res.data || []).map((p: RawProductResponse) => ({
        id: p.id,
        name: p.name || "Без названия",
        // Бэкенд может отдавать поля с префиксом ref_ или без него, берем то, что есть
        length_mm: (p.length_mm ?? p.ref_length_mm) || 0,
        width_mm: (p.width_mm ?? p.ref_width_mm) || 0,
        height_mm: (p.height_mm ?? p.ref_height_mm) || 0
      })) as Product[];
      
      setProducts(fetchedProducts.filter((p) => p.length_mm > 0 && p.width_mm > 0 && p.height_mm > 0));
    } catch (err) {
      console.error("Product fetch error:", err);
      setError('Не удалось загрузить справочник товаров');
    }
  };

  const addToCart = (product: Product) => {
    setCart(prev => {
      const existing = prev.find(item => item.product.id === product.id);
      if (existing) {
        return prev.map(item => 
          item.product.id === product.id 
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const removeFromCart = (productId: number) => {
    setCart(prev => prev.filter(item => item.product.id !== productId));
  };

  const updateQuantity = (productId: number, quantity: number) => {
    if (quantity <= 0) {
      removeFromCart(productId);
      return;
    }
    setCart(prev => prev.map(item => 
      item.product.id === productId ? { ...item, quantity } : item
    ));
  };

  const handleSolve = async () => {
    if (cart.length === 0) return;
    
    setLoading(true);
    setError(null);
    setPackResults(null);

    try {
      const payload = {
        items: cart.map(item => ({
          product_id: item.product.id,
          quantity: item.quantity
        }))
      };
      
      const res = await api.post<PackResult[]>('/api/v1/packing/solve-direct', payload);
      setPackResults(res.data);
      setSelectedVariant(0);

    } catch (err: unknown) {
      const error = err as ApiErrorResponse;
      setError(error.response?.data?.detail || 'Ошибка расчета упаковки');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-6">Расчет упаковки</h1>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Левая колонка: Справочник и Корзина */}
          <div className="lg:col-span-1 space-y-6">
            {/* Справочник товаров */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Справочник товаров</h2>
              <div className="space-y-2 max-h-[300px] overflow-y-auto">
                {products.length === 0 ? (
                  <p className="text-sm text-slate-500">Загрузка...</p>
                ) : (
                  products.map(p => (
                    <div key={p.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-slate-50 border border-transparent hover:border-slate-200">
                      <div>
                        <p className="font-medium text-slate-900 text-sm">{p.name}</p>
                        <p className="text-xs text-slate-500">{p.length_mm}x{p.width_mm}x{p.height_mm} мм</p>
                      </div>
                      <button 
                        onClick={() => addToCart(p)}
                        className="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-100 transition-colors"
                      >
                        + Добавить
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Корзина */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
              <h2 className="text-lg font-semibold text-slate-800 mb-3">Товары к упаковке</h2>
              {cart.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">Добавьте товары из справочника</p>
              ) : (
                <div className="space-y-3">
                  {cart.map(item => (
                    <div key={item.product.id} className="flex items-center justify-between bg-slate-50 p-2 rounded-lg">
                      <div className="flex-1 mr-2">
                        <p className="text-sm font-medium text-slate-900">{item.product.name}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <input 
                          type="number" 
                          min="1" 
                          value={item.quantity}
                          onChange={(e) => updateQuantity(item.product.id, parseInt(e.target.value) || 0)}
                          className="w-16 px-2 py-1 border border-slate-300 rounded-md text-center text-sm focus:ring-blue-500 focus:border-blue-500"
                        />
                        <button onClick={() => removeFromCart(item.product.id)} className="text-red-500 hover:text-red-700">
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      </div>
                    </div>
                  ))}
                  
                  <button
                    onClick={handleSolve}
                    disabled={loading}
                    className="w-full mt-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                  >
                    {loading ? 'Расчет...' : 'Рассчитать упаковку'}
                  </button>
                </div>
              )}
              
              {error && <p className="mt-3 text-sm text-red-600 bg-red-50 p-2 rounded-lg">{error}</p>}
            </div>
          </div>

          {/* Правая колонка: Визуализация */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 min-h-[500px]">
              {packResults ? (
                <PackVisualizer 
                  results={packResults} 
                  selectedVariant={selectedVariant} 
                  onSelect={setSelectedVariant} 
                />
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400 text-center p-8">
                  <div>
                    <svg className="w-16 h-16 mx-auto mb-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
                    <p className="font-medium">Здесь появится 3D-схема упаковки</p>
                    <p className="text-sm mt-1">Добавьте товары и нажмите &quot;Рассчитать&quot;</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}