import React, { useState } from 'react';
import type { OverrideTrendPoint } from '../../types/sentrax';

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
      <div className="surface space-y-1 p-4 sm:p-5">
        <h2 className="font-semibold">Daily override rate</h2>
        <p className="text-sm text-muted-foreground">{isLoading ? 'Loading override trend…' : 'No closure decisions in this range. Try a longer date range or clear the Wazuh rule filter.'}</p>
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
  const maxRate = 100;
  const maxExemplars = Math.max(1, ...data.map((d) => d.exemplar_count));

  const start = Date.parse(data[0].date);
  const duration = Date.parse(data[data.length - 1].date) - start;
  const points = data.map((d, index) => {
    const position = duration ? (Date.parse(d.date) - start) / duration : 0.5;
    const x = padding.left + position * chartWidth;
    const yRate = d.override_rate === null ? null : padding.top + chartHeight - (d.override_rate / maxRate) * chartHeight;
    const yExemplar = padding.top + chartHeight - (d.exemplar_count / maxExemplars) * chartHeight;
    return { ...d, x, yRate, yExemplar, index };
  });

  // Construct SVG paths
  const isConsecutive = (index: number) => index > 0
    && Date.parse(points[index].date) - Date.parse(points[index - 1].date) === 86_400_000;
  const ratePath = points.map((point, index) => {
    if (point.yRate === null) return '';
    const command = isConsecutive(index) && points[index - 1].yRate !== null ? 'L' : 'M';
    return `${command} ${point.x} ${point.yRate}`;
  }).join(' ');
  const exemplarPath = points.map((p, i) => `${isConsecutive(i) ? 'L' : 'M'} ${p.x} ${p.yExemplar}`).join(' ');

  const hoveredPoint = hoveredIndex !== null ? points[hoveredIndex] : null;

  return (
    <section className="surface p-4 sm:p-5 space-y-4" aria-labelledby="override-trend-title">
      {/* Header and Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-zinc-900">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <h2 id="override-trend-title" className="font-semibold">Daily override rate</h2>
          </div>
          <p className="text-xs text-zinc-400 font-sans">
            Each marker represents an observed day. The dashed series counts feedback examples created to date.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-3 text-xs self-start sm:self-auto">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full bg-cyan-400" />
            <span className="text-zinc-300">Override Rate (%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-0.5 border-t-2 border-dashed border-emerald-400" />
            <span className="text-zinc-400">Exemplars Created</span>
          </div>
        </div>
      </div>

      {/* SVG Container */}
      <div className="relative w-full overflow-hidden select-none">
        <svg
          role="img"
          aria-label="Daily override rates and cumulative feedback examples. The daily data table contains exact values."
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto overflow-visible font-mono"
        >
          {/* Grid lines & Y-axis labels */}
          {[0, 25, 50, 75, 100].map((val) => {
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
                  fill="#a1a1aa"
                >
                  {val}%
                </text>
              </g>
            );
          })}

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
                {p.yRate !== null && <circle
                  cx={p.x}
                  cy={p.yRate}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#06b6d4' : '#09090b'}
                  stroke="#06b6d4"
                  strokeWidth="2"
                />}

                {/* X-axis date label */}
                <text
                  x={p.x}
                  y={padding.top + chartHeight + 18}
                  textAnchor="middle"
                  fontSize="10"
                  fill={isHovered ? '#f4f4f5' : '#a1a1aa'}
                  fontWeight={isHovered ? 'bold' : 'normal'}
                >
                  {(p.index % Math.ceil(points.length / 8) === 0 || p.index === points.length - 1) && p.date.slice(5)}
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
              top: `${Math.max(10, ((hoveredPoint.yRate ?? hoveredPoint.yExemplar) / svgHeight) * 100 - 35)}%`,
              transform: 'translate(-50%, -100%)',
            }}
          >
            <div className="text-[10px] text-zinc-400 font-bold border-b border-zinc-800 pb-1">
              Date: {hoveredPoint.date}
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Override Rate:</span>
              <span className="text-cyan-300 font-bold">
                {hoveredPoint.override_rate === null ? 'Unavailable' : `${hoveredPoint.override_rate.toFixed(1)}%`}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Overrides:</span>
              <span className="text-zinc-200">
                {hoveredPoint.override_count} / {hoveredPoint.total_decisions ?? hoveredPoint.total_closed} decisions
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">Exemplars Created:</span>
              <span className="text-emerald-400 font-bold">{hoveredPoint.exemplar_count}</span>
            </div>
          </div>
        )}
      </div>

      <details className="border-t border-border pt-2">
        <summary className="cursor-pointer py-2 text-sm font-medium">View daily data</summary>
        <div className="table-region" role="region" tabIndex={0} aria-label="Daily override data">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Daily overrides and cumulative feedback examples</caption>
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="whitespace-nowrap p-2">Date (UTC)</th>
                <th scope="col" className="p-2 text-right">Closures</th>
                <th scope="col" className="p-2 text-right">Overrides</th>
                <th scope="col" className="p-2 text-right">Approvals and overrides</th>
                <th scope="col" className="p-2 text-right">Override rate</th>
                <th scope="col" className="p-2 text-right">Cumulative examples</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border tabular-nums">
              {data.map((point) => (
                <tr key={point.date}>
                  <th scope="row" className="whitespace-nowrap p-2 font-normal">{point.date}</th>
                  <td className="p-2 text-right">{point.total_closed}</td>
                  <td className="p-2 text-right">{point.override_count}</td>
                  <td className="p-2 text-right">{point.total_decisions ?? 'Unavailable'}</td>
                  <td className="p-2 text-right">{point.override_rate == null ? 'Unavailable' : `${point.override_rate.toFixed(1)}%`}</td>
                  <td className="p-2 text-right">{point.exemplar_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
};
