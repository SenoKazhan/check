// frontend/src/components/PackVisualizer.tsx
'use client';

import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, ContactShadows, Text } from '@react-three/drei'; 
import { useMemo, useState } from 'react';
import * as THREE from 'three'; 

export interface Placement {
  item_id: number;
  x_mm: number; y_mm: number; z_mm: number;
  length_mm: number; width_mm: number; height_mm: number;
  rotated: boolean;
}

export interface PackResult {
  box_l_mm: number; box_w_mm: number; box_h_mm: number;
  box_volume_cm3: number;
  placements: Placement[];
  variant_index: number;
}

const ITEM_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4'];

function Box3D({ position, size, color, label, opacity = 0.9 }: {
  position: [number, number, number];
  size: [number, number, number];
  color: string;
  label: string;
  opacity?: number;
}) {
  return (
    <group position={position}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial 
          color={color} 
          transparent 
          opacity={opacity} 
          roughness={0.4}
          metalness={0.1}
        />
      </mesh>
      {/* Чёрная обводка для четкости границ */}
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(...size)]} />
        <lineBasicMaterial color="#000000" linewidth={2} />
      </lineSegments>
      {/* Подпись с номером товара над объектом */}
      <Text
        position={[0, size[1] / 2 + 0.02, 0]}
        fontSize={0.03}
        color="#000"
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.005}
        outlineColor="#ffffff"
      >
        {label}
      </Text>
    </group>
  );
}

export default function PackVisualizer({ results, selectedVariant, onSelect }: {
  results: PackResult[];
  selectedVariant: number;
  onSelect: (idx: number) => void;
}) {
  
  const result = results[selectedVariant];
  const scale = 0.001; // мм -> метры
  const [showWireframe, setShowWireframe] = useState(false);

  const groupPosition = useMemo((): [number, number, number] => [
    -(result.box_l_mm * scale / 2),
    0,
    -(result.box_w_mm * scale / 2)
  ], [result]);

  const cameraPosition = useMemo((): [number, number, number] => {
    const maxDim = Math.max(result.box_l_mm, result.box_w_mm, result.box_h_mm) * scale;
    return [maxDim * 2.5, maxDim * 2, maxDim * 2.5];
  }, [result]);
  
  if (!results?.length) {
    return (
      <div className="p-8 text-center text-slate-500 bg-slate-50 rounded-xl border border-dashed border-slate-300">
        <p className="font-medium">Нет данных для визуализации</p>
      </div>
    );
  }
  


  return (
    <div className="space-y-4">
      {/* Панель управления */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
        <div className="flex gap-2 flex-wrap">
          {results.map((r, i) => (
            <button 
              key={i} 
              onClick={() => onSelect(i)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                i === selectedVariant 
                  ? 'bg-blue-600 text-white shadow-md' 
                  : 'bg-white text-slate-700 hover:bg-slate-100 border border-slate-200'
              }`}
            >
              Вариант {i+1} 
              <span className="ml-2 text-xs opacity-80">• {r.box_volume_cm3.toFixed(0)} см³</span>
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input 
              type="checkbox" 
              checked={showWireframe} 
              onChange={(e) => setShowWireframe(e.target.checked)} 
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            Каркас
          </label>
        </div>
      </div>
      
      {/* 3D Canvas */}
      <div className="border border-slate-200 rounded-xl bg-gradient-to-b from-slate-100 to-slate-200 overflow-hidden relative" style={{ height: '600px' }}>
        <Canvas 
          camera={{ position: cameraPosition, fov: 45 }}
          shadows
          dpr={[1, 2]} // Оптимизация для ретины
        >
          {/* Освещение */}
          <ambientLight intensity={0.6} />
          <directionalLight 
            position={[10, 20, 10]} 
            intensity={1.0} 
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-bias={-0.0001}
          />
          <directionalLight position={[-10, 5, -10]} intensity={0.4} />
          
          <group position={groupPosition}>
            {/* Контейнер (коробка) */}
            <Box3D
              position={[
                result.box_l_mm * scale / 2, 
                result.box_h_mm * scale / 2, 
                result.box_w_mm * scale / 2
              ]}
              size={[
                result.box_l_mm * scale, 
                result.box_h_mm * scale, 
                result.box_w_mm * scale
              ]}
              color="#94a3b8"
              label="Контейнер"
              opacity={showWireframe ? 0.05 : 0.1}
            />
            
            {/* Товары */}
            {result.placements.map((p, idx) => {
              // Маппинг осей: Backend -> Three.js
              // Backend X (Длина) -> Three.js X
              // Backend Z (Высота) -> Three.js Y (Up)
              // Backend Y (Ширина) -> Three.js Z (Depth)
              
              const sizeX = p.length_mm;
              const sizeY = p.height_mm;
              const sizeZ = p.width_mm;

              // Центр объекта = Координата угла + Половина размера
              const centerX = p.x_mm + sizeX / 2;
              const centerY = p.z_mm + sizeY / 2; // Z backend -> Y three.js (вверх!)
              const centerZ = p.y_mm + sizeZ / 2; // Y backend -> Z three.js (вглубь)

              return (
                <Box3D
                  key={`${p.item_id}-${idx}`}
                  position={[
                    centerX * scale, 
                    centerY * scale, 
                    centerZ * scale
                  ]}
                  size={[
                    sizeX * scale, 
                    sizeY * scale, 
                    sizeZ * scale
                  ]}
                  color={ITEM_COLORS[idx % ITEM_COLORS.length]}
                  label={`#${p.item_id}`}
                  opacity={showWireframe ? 0.3 : 0.85}
                />
              );
            })}
            
            {/* Оси координат (красный=X, зелёный=Y/высота, синий=Z) */}
            {/* Используем primitive, так как AxesHelper нет в drei */}
            <primitive 
              object={new THREE.AxesHelper(0.5)} 
              position={[0.02, 0.02, 0.02]} 
            />
          </group>
          
          {/* Пол с сеткой */}
          <Grid
            position={[0, -0.001, 0]}
            cellSize={0.05}
            sectionSize={0.2}
            fadeDistance={5}
            sectionColor="#64748b"
            cellColor="#94a3b8"
            infiniteGrid
          />
          
          {/* Тени от объектов на полу */}
          <ContactShadows 
            position={[0, 0, 0]} 
            opacity={0.4} 
            scale={2} 
            blur={2} 
            far={1} 
            resolution={1024}
          />
          
          {/* Управление камерой */}
          <OrbitControls 
            enablePan 
            minDistance={0.2} 
            maxDistance={5}
            target={[
              result.box_l_mm * scale / 2, 
              result.box_h_mm * scale / 3, 
              result.box_w_mm * scale / 2
            ]}
          />
        </Canvas>
      </div>
      
      {/* Инфо-панель с метриками */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[
          { label: 'Длина', value: `${result.box_l_mm.toFixed(1)} мм` },
          { label: 'Ширина', value: `${result.box_w_mm.toFixed(1)} мм` },
          { label: 'Высота', value: `${result.box_h_mm.toFixed(1)} мм` },
          { label: 'Объём', value: `${result.box_volume_cm3.toFixed(0)} см³` },
          { label: 'Товаров', value: result.placements.length.toString() },
          { label: 'Эффективность', 
            value: `${(result.placements.reduce((sum, p) => 
              sum + p.length_mm * p.width_mm * p.height_mm, 0
            ) / (result.box_l_mm * result.box_w_mm * result.box_h_mm) * 100).toFixed(1)}%` 
          }
        ].map(item => (
          <div key={item.label} className="bg-white p-3 rounded-lg border border-slate-200 text-center hover:border-blue-300 transition-colors">
            <div className="text-xs text-slate-500">{item.label}</div>
            <div className="font-bold text-slate-900">{item.value}</div>
          </div>
        ))}
      </div>
              {/* Легенда цветов */}
        <div className="flex flex-wrap gap-3 pt-2">
          <span className="text-xs text-slate-500">Товары:</span>
          {result.placements.map((p, i) => (
            // ИСПРАВЛЕНО: Используем индекс i как ключ, так как item_id может повторяться при quantity > 1
            <div key={i} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: ITEM_COLORS[i % ITEM_COLORS.length] }} />
              <span className="text-xs text-slate-600 font-medium">#{p.item_id}</span>
            </div>
          ))}
        </div>
    </div>
  );
}