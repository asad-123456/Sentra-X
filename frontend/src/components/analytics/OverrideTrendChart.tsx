import React, { useState } from 'react';
import type { OverrideTrendPoint } from '../../types/sentrax';
import { TrendingDown, Sparkles, BookmarkCheck } from 'lucide-react';

interface OverrideTrendChartProps {
  data: OverrideTrendPoint[];
  isLoading?: boolean;
}

export const OverrideTrendChart: React.FC<OverrideTrendChartProps> = ({
  data,
  isLoading = false,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (isLoading || !data || data.length === 0) {
    return (
      <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 h-[380px] flex items-center justify-center text-zinc-500 font-mono text-xs">
        Loading longitudinal trendline telemetry...
      </div>
    );
  }

  // Chart dimensions & coordinates
  const svgWidth = 800;
  const svgHeight = 240;
  const padding = { top: 25, right: 40, bottom: 35, left: 45 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  // Max bounds
  const maxRate = 25; // 0% to 25% on Y-left
  const maxExemplars = Math.max(40, ...data.map((d) => d.exemplar_count));

  const points = data.map((d, index) => {
    const x = padding.left + (index / (data.length - 1)) * chartWidth;
    const yRate = padding.top + chartHeight - (d.override_rate / maxRate) * chartHeight;
    const yExemplar = padding.top + chartHeight - (d.exemplar_count / maxExemplars) * chartHeight;
    return { ...d, x, yRate, yExemplar, index };
  });

  // Construct SVG paths
  const ratePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.yRate}`).join(' ');
  const areaPath = `${ratePath} L ${points[points.length - 1].x} ${padding.top + chartHeight} L ${points[0].x} ${padding.top + chartHeight} Z`;
  const exemplarPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.yExemplar}`).join(' ');

  // Calculate improvement delta
  const initialRate = data[0]?.override_rate || 0;
  const latestRate = data[data.length - 1]?.override_rate || 0;
  const relativeReduction =
    initialRate > 0 ? (((initialRate - latestRate) / initialRate) * 100).toFixed(1) : '0';

  const hoveredPoint = hoveredIndex !== null ? points[hoveredIndex] : null;

  return (
    <div className="p-5 rounded-xl bg-zinc-950 border border-zinc-850 space-y-4">
      {/* Header and Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-zinc-900">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-zinc-100 uppercase tracking-wider">
              Longitudinal Override Rate &amp; Calibration Impact
            </span>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800/80">
              <Sparkles className="size-2.5 text-cyan-400" />
              <span>Few-Shot Effect</span>
            </span>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Tracking reduction in repeat human overrides as dynamic few-shot exemplars accumulate
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs font-mono self-start sm:self-auto">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-cyan-400" />
            <span className="text-zinc-300">Override Rate (%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 border-t-2 border-dashed border-emerald-400" />
            <span className="text-zinc-400">Active Exemplars</span>
          </div>
        </div>
      </div>

      {/* SVG Container */}
      <div className="relative w-full overflow-hidden select-none">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible font-mono"
        >
          <defs>
            {/* Area gradient for override rate */}
            <linearGradient id="rateGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines & Y-axis labels */}
          {[0, 5, 10, 15, 20, 25].map((val) => {
            const y = padding.top + chartHeight - (val / maxRate) * chartHeight;
            return (
              <g key={val}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={svgWidth - padding.right}
                  y2={y}
                  stroke="#27272a"
                  strokeWidth="1"
                  strokeDasharray={val === 0 ? undefined : '3 3'}
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  fontSize="10"
                  fill="#71717a"
                >
                  {val}%
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          <path d={areaPath} fill="url(#rateGradient)" />

          {/* Exemplar line (dashed emerald) */}
          <path
            d={exemplarPath}
            fill="none"
            stroke="#10b981"
            strokeWidth="1.5"
            strokeDasharray="4 4"
            className="opacity-75"
          />

          {/* Rate line (solid cyan) */}
          <path d={ratePath} fill="none" stroke="#06b6d4" strokeWidth="2.5" />

          {/* Hover guideline */}
          {hoveredPoint && (
            <line
              x1={hoveredPoint.x}
              y1={padding.top}
              x2={hoveredPoint.x}
              y2={padding.top + chartHeight}
              stroke="#52525b"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
          )}

          {/* Data Points */}
          {points.map((p) => {
            const isHovered = hoveredIndex === p.index;
            return (
              <g
                key={p.index}
                className="cursor-pointer"
                onMouseEnter={() => setHoveredIndex(p.index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Transparent hit target */}
                <rect
                  x={p.x - 18}
                  y={padding.top}
                  width="36"
                  height={chartHeight}
                  fill="transparent"
                />

                {/* Exemplar point */}
                <circle
                  cx={p.x}
                  cy={p.yExemplar}
                  r={isHovered ? 4.5 : 3}
                  fill="#09090b"
                  stroke="#10b981"
                  strokeWidth="1.5"
                />

                {/* Rate point */}
                <circle
                  cx={p.x}
                  cy={p.yRate}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#06b6d4' : '#09090b'}
                  stroke="#06b6d4"
                  strokeWidth="2"
                />

                {/* X-axis date label */}
                <text
                  x={p.x}
                  y={padding.top + chartHeight + 18}
                  textAnchor="middle"
                  fontSize="10"
                  fill={isHovered ? '#f4f4f5' : '#71717a'}
                  fontWeight={isHovered ? 'bold' : 'normal'}
                >
                  {p.date.slice(5)}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Floating Tooltip Card */}
        {hoveredPoint && (
          <div
            className="absolute z-10 pointer-events-none p-2.5 rounded-lg bg-zinc-900 border border-zinc-700 shadow-xl text-xs font-mono space-y-1"
            style={{
              left: `${(hoveredPoint.x / svgWidth) * 100}%`,
              top: `${Math.max(10, (hoveredPoint.yRate / svgHeight) * 100 - 35)}%`,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <div className="text-[10px] text-zinc-400 font-bold border-b border-zinc-800 pb-1">
              Date: {hoveredPoint.date}
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Override Rate:</span>
              <span className="text-cyan-300 font-bold">{hoveredPoint.override_rate.toFixed(1)}%</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Overrides:</span>
              <span className="text-zinc-200">
                {hoveredPoint.override_count} / {hoveredPoint.total_closed} closed
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Active Exemplars:</span>
              <span className="text-emerald-400 font-bold">{hoveredPoint.exemplar_count}</span>
            </div>
          </div>
        )}
      </div>

      {/* Metric Callout Footer Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-zinc-900 text-xs font-mono">
        <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-850">
          <span className="text-[10px] text-zinc-500 uppercase">Initial Override Rate</span>
          <div className="text-base font-bold text-zinc-300 pt-0.5">{initialRate.toFixed(1)}%</div>
          <span className="text-[10px] text-zinc-500 font-sans">Prior to exemplar seeding</span>
        </div>

        <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-850">
          <span className="text-[10px] text-zinc-500 uppercase">Current Override Rate</span>
          <div className="text-base font-bold text-cyan-400 pt-0.5">{latestRate.toFixed(1)}%</div>
          <span className="text-[10px] text-zinc-500 font-sans">Active production triage</span>
        </div>

        <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-850">
          <span className="text-[10px] text-zinc-500 uppercase">Relative Reduction</span>
          <div className="text-base font-bold text-emerald-400 pt-0.5 flex items-center gap-1">
            <TrendingDown className="size-4" />
            <span>-{relativeReduction}%</span>
          </div>
          <span className="text-[10px] text-zinc-500 font-sans">Repeat override prevention</span>
        </div>

        <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-850">
          <span className="text-[10px] text-zinc-500 uppercase">Cumulative Exemplars</span>
          <div className="text-base font-bold text-emerald-300 pt-0.5 flex items-center gap-1">
            <BookmarkCheck className="size-4 text-emerald-400" />
            <span>{data[data.length - 1]?.exemplar_count || 0}</span>
          </div>
          <span className="text-[10px] text-zinc-500 font-sans">Indexed prompt exemplars</span>
        </div>
      </div>
    </div>
  );
};

