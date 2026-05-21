// frontend/src/app/products/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useAuth } from '@/providers/AuthProvider';
import { useRouter } from 'next/navigation';
import { hasPermission, Permission } from '@/lib/permissions';

interface Product {
  id: number;
  name: string;
  length_mm: number;
  width_mm: number;
  height_mm: number;
  qr_code: string | null;
}

export default function ProductsPage() {
  const { user } = useAuth();
  const router = useRouter();
  
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user && !hasPermission(user.role, Permission.MANAGE_PRODUCTS)) {
      router.push('/');
    }
  }, [user, router]);

  useEffect(() => {
    fetchProducts();
  }, []);

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const res = await api.get('/api/v1/products/');
      setProducts(res.data);
    } catch {
      setError('Не удалось загрузить товары');
    } finally {
      setLoading(false);
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
        <h1 className="text-3xl font-bold text-slate-900 mb-6">Справочник товаров</h1>
        
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase w-12">ID</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">Наименование</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">Габариты (Д x Ш x В)</th>
                  <th className="p-4 text-xs font-semibold text-slate-600 uppercase">QR-код</th>
                </tr>
              </thead>
              <tbody>
                {products.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8 text-center text-slate-400">Справочник пуст</td>
                  </tr>
                ) : (
                  products.map(p => (
                    <tr key={p.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="p-4 text-sm text-slate-500">{p.id}</td>
                      <td className="p-4 text-sm font-medium text-slate-900">{p.name}</td>
                      <td className="p-4 text-sm text-slate-700 font-mono">
                        {p.length_mm || 0} x {p.width_mm || 0} x {p.height_mm || 0} мм
                      </td>
                      <td className="p-4 text-sm text-slate-500">
                        {p.qr_code || '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}