'use client';
import UploadPanel from "@/components/UploadPanel";

export default function MeasurePage() {
  return (
    <div className="min-h-screen bg-gray-50 py-10">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-center text-gray-900 mb-8">
          Измерение габаритов
        </h1>
        <UploadPanel />
      </div>
    </div>
  );
}