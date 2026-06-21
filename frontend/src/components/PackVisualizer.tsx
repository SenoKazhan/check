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

function getItemColor(index: number, total: number): string {
  const hue = (index * (360 / Math.max(total, 1)) + (index * 47)) % 360;
  return `hsl(${hue.toFixed(0)}, 62%, 52%)`;
}

function Box3D({ position, size, color, label, opacity = 1, isContainer = false }: {
  position: [number, number, number];
  size: [number, number, number];
  color: string;
  label: string;
  opacity?: number;
  isContainer?: boolean;
}) {
  const isTransparent = opacity < 0.999;

  return (
    <group position={position}>
      <mesh castShadow={!isContainer} receiveShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial
          color={color}
          transparent={isTransparent}
          opacity={opacity}
          roughness={0.85}
          metalness={0}
          flatShading
          depthWrite={!isTransparent}
          polygonOffset
          polygonOffsetFactor={1}
          polygonOffsetUnits={1}
        />
      </mesh>
      <lineSegments renderOrder={1}>
        <edgesGeometry args={[new THREE.BoxGeometry(...size)]} />
        <lineBasicMaterial color="#1e293b" linewidth={1.5} />
      </lineSegments>
      {!isContainer && (
        <Text
          position={[0, size[1] / 2 + 0.018, 0]}
          fontSize={0.026}
          color="#0f172a"
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.004}
          outlineColor="#ffffff"
        >
          {label}
        </Text>
      )}
    </group>
  );
}

export default function PackVisualizer({ results, selectedVariant, onSelect }: {
  results: PackResult[];
  selectedVariant: number;
  onSelect: (idx: number) => void;
}) {

  const result = results[selectedVariant];
  const scale = 0.001;
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

  const itemCount = result?.placements.length ?? 0;

  if (!results?.length) {
    return (
      <div className="p-8 text-center text-slate-500 bg-slate-50 rounded-xl border border-dashed border-slate-300">
        <p className="font-medium">Нет данных для визуализации</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
              Вариант {i + 1}
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

      <div className="border border-slate-200 rounded-xl bg-gradient-to-b from-slate-100 to-slate-200 overflow-hidden relative" style={{ height: '600px' }}>
        <Canvas
          camera={{ position: cameraPosition, fov: 45 }}
          shadows
          dpr={[1, 2]}
          gl={{ antialias: true, alpha: false }}
        >
          <ambientLight intensity={0.7} />
          <directionalLight
            position={[10, 20, 10]}
            intensity={0.9}
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-bias={-0.0001}
          />
          <directionalLight position={[-10, 5, -10]} intensity={0.35} />

          <group position={groupPosition}>
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
              opacity={showWireframe ? 0.04 : 0.08}
              isContainer
            />

            {result.placements.map((p, idx) => {
              const sizeX = p.length_mm;
              const sizeY = p.height_mm;
              const sizeZ = p.width_mm;

              const centerX = p.x_mm + sizeX / 2;
              const centerY = p.z_mm + sizeY / 2;
              const centerZ = p.y_mm + sizeZ / 2;

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
                  color={getItemColor(idx, itemCount)}
                  label={`#${p.item_id}`}
                  opacity={showWireframe ? 0.35 : 1}
                />
              );
            })}

            <primitive
              object={new THREE.AxesHelper(0.5)}
              position={[0.02, 0.02, 0.02]}
            />
          </group>

          <Grid
            position={[0, -0.001, 0]}
            cellSize={0.05}
            sectionSize={0.2}
            fadeDistance={5}
            sectionColor="#64748b"
            cellColor="#94a3b8"
            infiniteGrid
          />

          <ContactShadows
            position={[0, 0, 0]}
            opacity={0.4}
            scale={2}
            blur={2}
            far={1}
            resolution={1024}
          />

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

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[
          { label: 'Длина', value: `${result.box_l_mm.toFixed(1)} мм` },
          { label: 'Ширина', value: `${result.box_w_mm.toFixed(1)} мм` },
          { label: 'Высота', value: `${result.box_h_mm.toFixed(1)} мм` },
          { label: 'Объём', value: `${result.box_volume_cm3.toFixed(0)} см³` },
          { label: 'Товаров', value: result.placements.length.toString() },
          {
            label: 'Эффективность',
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
      <div className="flex flex-wrap gap-3 pt-2">
        <span className="text-xs text-slate-500">Товары:</span>
        {result.placements.map((p, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: getItemColor(i, itemCount) }} />
            <span className="text-xs text-slate-600 font-medium">#{p.item_id}</span>
          </div>
        ))}
      </div>
    </div>
  );
}