import React, { useState } from 'react';
import { BarChart3, TrendingUp, Activity, Grid } from 'lucide-react';

export const AnalyticalChart = ({ chartData }) => {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [activeTypeOverride, setActiveTypeOverride] = useState(null);

  if (!chartData || chartData.recommended === false) {
    return null;
  }

  const effectiveType = activeTypeOverride || chartData.chart_type || 'bar';
  const title = chartData.title;
  const x_axis = chartData.x_axis || chartData.x_axis_label;
  const y_axis = chartData.y_axis || chartData.y_axis_label;
  const data_points = chartData.data_points;
  const trendline = chartData.trendline;
  const matrix = chartData.matrix;
  const categories = chartData.categories;
  const reason = chartData.reason;

  // Correlation Heatmap View
  if (effectiveType === 'heatmap' && matrix && categories && categories.length > 0) {
    return (
      <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-5 shadow-xs space-y-3">
        <div className="flex items-center justify-between border-b border-[#F1F5F9] dark:border-[#1E293B] pb-3">
          <div className="flex items-center gap-2">
            <Grid className="w-4 h-4 text-[#2563EB]" />
            <h4 className="text-xs font-bold text-[#0F172A] dark:text-white">{title || 'Correlation Matrix Heatmap'}</h4>
          </div>
          <span className="font-semibold uppercase tracking-wider px-2 py-0.5 rounded bg-blue-50 text-[#2563EB] border border-blue-200 text-[10px]">
            HEATMAP
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-center border-collapse">
            <thead>
              <tr>
                <th className="p-2 border border-slate-200 dark:border-[#1E293B] bg-slate-50 dark:bg-[#131F3F] text-left font-semibold text-slate-700 dark:text-slate-200">Feature</th>
                {categories.map((c, i) => (
                  <th key={i} className="p-2 border border-slate-200 dark:border-[#1E293B] bg-slate-50 dark:bg-[#131F3F] font-semibold text-slate-700 dark:text-slate-200 truncate max-w-[100px]" title={c}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {categories.map((rowCat, rIdx) => (
                <tr key={rIdx}>
                  <td className="p-2 border border-slate-200 dark:border-[#1E293B] bg-slate-50 dark:bg-[#131F3F] text-left font-semibold text-slate-700 dark:text-slate-200 truncate max-w-[120px]" title={rowCat}>
                    {rowCat}
                  </td>
                  {matrix[rIdx]?.map((val, cIdx) => {
                    const isSelf = rIdx === cIdx;
                    const r = val !== null && val !== undefined ? val : 0;
                    // Color mapping: +1 = blue, -1 = red, 0 = white
                    let bg = '#FFFFFF';
                    let textCol = '#0F172A';
                    if (isSelf) {
                      bg = '#F1F5F9';
                    } else if (r > 0) {
                      const alpha = Math.min(Math.abs(r), 1);
                      bg = `rgba(37, 99, 235, ${alpha * 0.4})`;
                    } else if (r < 0) {
                      const alpha = Math.min(Math.abs(r), 1);
                      bg = `rgba(239, 68, 68, ${alpha * 0.4})`;
                    }

                    return (
                      <td
                        key={cIdx}
                        className="p-2 border border-slate-200 font-mono text-[11px] font-medium transition-colors hover:brightness-95"
                        style={{ backgroundColor: bg, color: textCol }}
                        title={`${rowCat} ↔ ${categories[cIdx]}: r = ${r}`}
                      >
                        {val !== null && val !== undefined ? val.toFixed(2) : '—'}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Filter valid numeric data points
  const validPoints = (data_points || []).filter(
    (p) => p && typeof p.value === 'number' && !isNaN(p.value)
  );

  if (validPoints.length === 0) {
    return null;
  }

  // Calculate bounds
  const values = validPoints.map((p) => p.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const safeMax = maxVal === minVal ? (maxVal > 0 ? maxVal * 1.2 : 10) : maxVal;
  const safeMin = minVal < 0 ? minVal : 0;
  const range = safeMax - safeMin || 1;

  // SVG dimensions
  const svgWidth = 640;
  const svgHeight = 240;
  const padding = { top: 25, right: 30, bottom: 45, left: 60 };
  const chartWidth = svgWidth - padding.left - padding.right;
  const chartHeight = svgHeight - padding.top - padding.bottom;

  const getYPos = (val) => {
    const ratio = (val - safeMin) / range;
    return padding.top + chartHeight - ratio * chartHeight;
  };

  const getXPos = (idx) => {
    if (validPoints.length === 1) return padding.left + chartWidth / 2;
    return padding.left + (idx / (validPoints.length - 1)) * chartWidth;
  };

  const formatNumber = (num) => {
    if (num === null || num === undefined || isNaN(num)) return '—';
    if (Math.abs(num) >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (Math.abs(num) >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return Number.isInteger(num) ? String(num) : num.toFixed(2);
  };

  return (
    <div className="bg-white dark:bg-[#0F172A] border border-[#E2E8F0] dark:border-[#1E293B] rounded-2xl p-5 shadow-xs space-y-3">
      {/* Chart Header with Interactive Type Toggles */}
      <div className="flex items-center justify-between border-b border-[#F1F5F9] dark:border-[#1E293B] pb-3">
        <div className="flex items-center gap-2">
          {effectiveType === 'line' ? (
            <TrendingUp className="w-4 h-4 text-[#2563EB]" />
          ) : effectiveType === 'scatter' ? (
            <Activity className="w-4 h-4 text-[#2563EB]" />
          ) : (
            <BarChart3 className="w-4 h-4 text-[#2563EB]" />
          )}
          <h4 className="text-xs font-bold text-[#0F172A] dark:text-white">{title || 'Analytical Visualization'}</h4>
        </div>

        {/* View mode toggle chips */}
        <div className="flex items-center gap-1.5 text-[10px]">
          <button
            onClick={() => setActiveTypeOverride('bar')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              effectiveType === 'bar'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 dark:bg-[#131F3F] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#1E293B]'
            }`}
          >
            Bar
          </button>
          <button
            onClick={() => setActiveTypeOverride('line')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              effectiveType === 'line'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 dark:bg-[#131F3F] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#1E293B]'
            }`}
          >
            Line
          </button>
          <button
            onClick={() => setActiveTypeOverride('scatter')}
            className={`px-2 py-0.5 rounded font-medium transition-colors ${
              effectiveType === 'scatter'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-100 dark:bg-[#131F3F] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#1E293B]'
            }`}
          >
            Scatter
          </button>
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative overflow-x-auto">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-auto max-h-64 select-none"
        >
          <defs>
            <linearGradient id="lineAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563EB" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#2563EB" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines (horizontal) */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = padding.top + chartHeight * (1 - pct);
            const val = safeMin + range * pct;
            return (
              <g key={idx}>
                <line
                  x1={padding.left}
                  y1={y}
                  x2={svgWidth - padding.right}
                  y2={y}
                  stroke="#F1F5F9"
                  strokeWidth="1"
                  strokeDasharray={idx === 0 ? '0' : '4 4'}
                />
                <text
                  x={padding.left - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="text-[9px] fill-[#94A3B8] font-mono"
                >
                  {formatNumber(val)}
                </text>
              </g>
            );
          })}

          {/* BAR CHART RENDERING */}
          {effectiveType === 'bar' && (() => {
            const slotWidth = chartWidth / validPoints.length;
            const barWidth = Math.max(8, Math.min(slotWidth * 0.65, 36));

            return validPoints.map((pt, idx) => {
              const x = padding.left + idx * slotWidth + (slotWidth - barWidth) / 2;
              const y = getYPos(pt.value);
              const height = padding.top + chartHeight - y;
              const isHovered = hoveredPoint === idx;

              return (
                <g
                  key={idx}
                  onMouseEnter={() => setHoveredPoint(idx)}
                  onMouseLeave={() => setHoveredPoint(null)}
                  className="cursor-pointer"
                >
                  <rect
                    x={x}
                    y={y}
                    width={barWidth}
                    height={Math.max(2, height)}
                    rx="3"
                    fill={isHovered ? '#1D4ED8' : '#2563EB'}
                    className="transition-colors duration-150"
                  />
                  {/* Category X Label */}
                  <text
                    x={x + barWidth / 2}
                    y={padding.top + chartHeight + 14}
                    textAnchor="middle"
                    className="text-[9px] fill-[#64748B] font-medium"
                  >
                    {pt.label ? (pt.label.length > 9 ? pt.label.slice(0, 8) + '…' : pt.label) : ''}
                  </text>
                </g>
              );
            });
          })()}

          {/* LINE CHART RENDERING */}
          {effectiveType === 'line' && (() => {
            const pointsCoords = validPoints.map((pt, idx) => `${getXPos(idx)},${getYPos(pt.value)}`);
            const polylinePoints = pointsCoords.join(' ');
            const areaPoints = `${getXPos(0)},${padding.top + chartHeight} ${polylinePoints} ${getXPos(validPoints.length - 1)},${padding.top + chartHeight}`;

            return (
              <g>
                <polygon points={areaPoints} fill="url(#lineAreaGradient)" />
                <polyline
                  fill="none"
                  stroke="#2563EB"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  points={polylinePoints}
                />
                {validPoints.map((pt, idx) => {
                  const cx = getXPos(idx);
                  const cy = getYPos(pt.value);
                  const isHovered = hoveredPoint === idx;

                  return (
                    <g
                      key={idx}
                      onMouseEnter={() => setHoveredPoint(idx)}
                      onMouseLeave={() => setHoveredPoint(null)}
                      className="cursor-pointer"
                    >
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isHovered ? 6 : 4}
                        fill={isHovered ? '#1D4ED8' : '#2563EB'}
                        stroke="#FFFFFF"
                        strokeWidth="2"
                        className="transition-all duration-150"
                      />
                      <text
                        x={cx}
                        y={padding.top + chartHeight + 14}
                        textAnchor="middle"
                        className="text-[9px] fill-[#64748B] font-medium"
                      >
                        {pt.label ? (pt.label.length > 8 ? pt.label.slice(0, 7) + '…' : pt.label) : ''}
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })()}

          {/* SCATTER PLOT RENDERING */}
          {effectiveType === 'scatter' && (() => {
            return (
              <g>
                {/* Regression Trendline (if provided) */}
                {(() => {
                  const tPoints = Array.isArray(trendline) ? trendline : (trendline?.points || []);
                  if (!tPoints || tPoints.length < 2) return null;
                  const x1 = getXPos(0);
                  const y1 = getYPos(tPoints[0].y);
                  const x2 = getXPos(validPoints.length - 1);
                  const y2 = getYPos(tPoints[1].y);
                  return (
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="#EF4444"
                      strokeWidth="2"
                      strokeDasharray="4 4"
                    />
                  );
                })()}

                {validPoints.map((pt, idx) => {
                  const cx = getXPos(idx);
                  const cy = getYPos(pt.value);
                  const isHovered = hoveredPoint === idx;

                  return (
                    <g
                      key={idx}
                      onMouseEnter={() => setHoveredPoint(idx)}
                      onMouseLeave={() => setHoveredPoint(null)}
                      className="cursor-pointer"
                    >
                      <circle
                        cx={cx}
                        cy={cy}
                        r={isHovered ? 7 : 5}
                        fill={isHovered ? '#1D4ED8' : 'rgba(37, 99, 235, 0.75)'}
                        stroke="#2563EB"
                        strokeWidth="1.5"
                        className="transition-all duration-150"
                      />
                      <text
                        x={cx}
                        y={padding.top + chartHeight + 14}
                        textAnchor="middle"
                        className="text-[9px] fill-[#64748B] font-medium"
                      >
                        {pt.label ? (pt.label.length > 8 ? pt.label.slice(0, 7) + '…' : pt.label) : ''}
                      </text>
                    </g>
                  );
                })}
              </g>
            );
          })()}

          {/* Axis Labels */}
          {x_axis && (
            <text
              x={svgWidth / 2}
              y={svgHeight - 4}
              textAnchor="middle"
              className="text-[9px] fill-[#94A3B8] font-medium"
            >
              {x_axis}
            </text>
          )}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoveredPoint !== null && validPoints[hoveredPoint] && (
          <div
            className="absolute top-2 right-4 bg-slate-900 text-white px-3 py-1.5 rounded-lg text-xs shadow-md pointer-events-none z-10 flex items-center gap-2 animate-in fade-in duration-100"
          >
            <span className="text-slate-400 font-medium">
              {validPoints[hoveredPoint].label || `Item ${hoveredPoint + 1}`}:
            </span>
            <span className="font-bold text-white font-mono">
              {formatNumber(validPoints[hoveredPoint].value)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
