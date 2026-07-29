"use client";

/** Circular 0~100% gauge used while AI analysis is running.
 *  Pure SVG (no chart lib) so it stays lightweight and animates smoothly
 *  via stroke-dashoffset transitions between polling updates. */
export function ProgressGauge({ percent, size = 96 }: { percent: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, percent));
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-slate-200"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="stroke-brand-600 transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <span className="absolute text-lg font-bold text-brand-700">{clamped}%</span>
    </div>
  );
}
