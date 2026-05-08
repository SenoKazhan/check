"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";

interface Product {
  id: number;
  name: string;
  qr_code: string | null;
  ref_length_mm: number | null;
  ref_width_mm: number | null;
  ref_height_mm: number | null;
  notes: string | null;
}

export default function ProductsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "", qr_code: "", ref_length_mm: "", ref_width_mm: "", ref_height_mm: "", notes: ""
  });

  // Защита от не-админов
  useEffect(() => {
    if (!authLoading && (!user || user.role !== "admin")) {
      router.push("/");
    }
  }, [user, authLoading, router]);

  const fetchProducts = async () => {
    try {
      const { data } = await api.get("/products/");
      setProducts(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProducts(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: any = { name: formData.name };
      if (formData.qr_code) payload.qr_code = formData.qr_code;
      ["ref_length_mm", "ref_width_mm", "ref_height_mm"].forEach(k => {
        if (formData[k as keyof typeof formData]) payload[k] = parseFloat(formData[k as keyof typeof formData]);
      });
      if (formData.notes) payload.notes = formData.notes;

      await api.post("/products/", payload);
      setIsFormOpen(false);
      setFormData({ name: "", qr_code: "", ref_length_mm: "", ref_width_mm: "", ref_height_mm: "", notes: "" });
      fetchProducts();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Ошибка добавления товара");
    }
  };

  if (authLoading || loading) return <p className="p-8 text-center text-gray-500">Загрузка справочника...</p>;
  if (!user || user.role !== "admin") return null;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Справочник товаров</h1>
        <button onClick={() => setIsFormOpen(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          + Добавить товар
        </button>
      </div>

      {isFormOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <form onSubmit={handleSubmit} className="bg-white rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="text-xl font-semibold">Новый товар</h2>
            <input required placeholder="Название" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
            <input placeholder="QR-код (опционально)" value={formData.qr_code} onChange={e => setFormData({...formData, qr_code: e.target.value})} className="w-full p-2 border border-gray-300 rounded-lg" />
            <div className="grid grid-cols-3 gap-3">
              <input type="number" step="0.1" placeholder="Длина (мм)" value={formData.ref_length_mm} onChange={e => setFormData({...formData, ref_length_mm: e.target.value})} className="p-2 border rounded-lg" />
              <input type="number" step="0.1" placeholder="Ширина (мм)" value={formData.ref_width_mm} onChange={e => setFormData({...formData, ref_width_mm: e.target.value})} className="p-2 border rounded-lg" />
              <input type="number" step="0.1" placeholder="Высота (мм)" value={formData.ref_height_mm} onChange={e => setFormData({...formData, ref_height_mm: e.target.value})} className="p-2 border rounded-lg" />
            </div>
            <textarea placeholder="Примечания" value={formData.notes} onChange={e => setFormData({...formData, notes: e.target.value})} className="w-full p-2 border rounded-lg resize-none" rows={2} />
            <div className="flex justify-end gap-3 mt-4">
              <button type="button" onClick={() => setIsFormOpen(false)} className="px-4 py-2 border rounded-lg hover:bg-gray-50">Отмена</button>
              <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Сохранить</button>
            </div>
          </form>
        </div>
      )}

      <div className="overflow-x-auto bg-white rounded-xl shadow border border-gray-200">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="p-4 font-medium text-gray-700">ID</th>
              <th className="p-4 font-medium text-gray-700">Название</th>
              <th className="p-4 font-medium text-gray-700">QR</th>
              <th className="p-4 font-medium text-gray-700">Эталон (мм)</th>
              <th className="p-4 font-medium text-gray-700">Примечания</th>
            </tr>
          </thead>
          <tbody>
            {products.map(p => (
              <tr key={p.id} className="border-b hover:bg-gray-50 transition-colors">
                <td className="p-4 text-gray-500">{p.id}</td>
                <td className="p-4 font-medium text-gray-900">{p.name}</td>
                <td className="p-4 font-mono text-sm text-gray-600">{p.qr_code || "—"}</td>
                <td className="p-4 text-gray-700">
                  {[p.ref_length_mm, p.ref_width_mm, p.ref_height_mm].filter(Boolean).join(" × ") || "—"}
                </td>
                <td className="p-4 text-gray-600 truncate max-w-xs">{p.notes || "—"}</td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr><td colSpan={5} className="p-6 text-center text-gray-500">Справочник пуст. Добавьте первый товар.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}