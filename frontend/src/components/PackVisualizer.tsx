'use client';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html, Grid } from '@react-three/drei';
import { useMemo } from 'react';
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

function Box3D({ position, size, color, label }: {
  position: [number, number, number];
  size: [number, number, number];
  color: string;
  label?: string;
}) {
  return (
    <mesh position={position}>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} transparent opacity={0.85} />
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(...size)]} />
        <lineBasicMaterial color="#000" linewidth={1} />
      </lineSegments>
      {label && (
        <Html position={[0, size[1]/2 + 0.02, 0]} center>
          <span className="text-[10px] bg-black/70 text-white px-1.5 py-0.5 rounded">
            {label}
          </span>
        </Html>
      )}
    </mesh>
  );
}

export default function PackVisualizer({ 
  results, 
  selectedVariant, 
  onSelect 
}: {
  results: PackResult[];
  selectedVariant: number;
  onSelect: (idx: number) => void;
}) {
  if (!results?.length) return <div className="p-6 text-gray-500">Нет данных для визуализации</div>;
  
  const result = results[selectedVariant];
  const scale = 0.001; // mm → meters
  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE'];
  
  return (
    <div className="space-y-4">
      {/* Переключатель вариантов */}
      <div className="flex gap-2 flex-wrap">
        {results.map((r, i) => (
          <button
            key={i}
            onClick={() => onSelect(i)}
            className={`px-3 py-1.5 rounded border text-sm transition ${
              i === selectedVariant 
                ? 'bg-blue-600 text-white border-blue-600' 
                : 'bg-white hover:border-blue-400'
            }`}
          >
            Вариант {i+1} • {r.box_volume_cm3.toFixed(0)} см³
          </button>
        ))}
      </div>
      
      {/* 3D Canvas */}
      <div className="border rounded-lg bg-gray-50" style={{ height: '450px' }}>
        <Canvas camera={{ position: [0.8, 0.8, 0.8], fov: 45 }}>
          <ambientLight intensity={0.6} />
          <directionalLight position={[5, 10, 5]} intensity={0.8} />
          
          {/* Контейнер */}
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
            color="#999"
            label="Контейнер"
          />
          
          {/* Товары */}
          {result.placements.map((p, idx) => {
            const [l, w, h] = p.rotated 
              ? [p.width_mm, p.length_mm, p.height_mm]
              : [p.length_mm, p.width_mm, p.height_mm];
            return (
              <Box3D
                key={`${p.item_id}-${idx}`}
                position={[
                  p.x_mm * scale + l * scale / 2,
                  p.z_mm * scale + h * scale / 2, // Z→Y в Three.js
                  p.y_mm * scale + w * scale / 2  // Y→Z в Three.js
                ]}
                size={[l * scale, h * scale, w * scale]}
                color={colors[idx % colors.length]}
                label={`#${p.item_id}`}
              />
            );
          })}
          
          <Grid position={[0, -0.001, 0]} cellSize={0.05} sectionSize={0.2} fadeDistance={2} />
          <OrbitControls enablePan minDistance={0.3} maxDistance={3} />
        </Canvas>
      </div>
      
      {/* Инфо-панель */}
      <div className="grid grid-cols-4 gap-3 text-sm">
        {[
          { label: 'Длина', value: `${result.box_l_mm.toFixed(1)} мм` },
          { label: 'Ширина', value: `${result.box_w_mm.toFixed(1)} мм` },
          { label: 'Высота', value: `${result.box_h_mm.toFixed(1)} мм` },
          { label: 'Объём', value: `${result.box_volume_cm3.toFixed(0)} см³` }
        ].map(item => (
          <div key={item.label} className="bg-gray-50 p-2.5 rounded text-center">
            <div className="text-gray-500 text-xs">{item.label}</div>
            <div className="font-semibold">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}