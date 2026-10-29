import { useState } from "react";
import type { ComparisonPoint } from "./types";
import { TerminalPanel } from "./Terminal";
export default function ComparisonChart({
  points,
  symbol,
}: {
  points: ComparisonPoint[];
  symbol: string;
}) {
  const [cursor, setCursor] = useState<number | null>(null);
  if (!points.length)
    return <TerminalPanel title="Indexed performance">NO DATA</TerminalPanel>;
  const width = 900,
    height = 300,
    left = 48,
    right = 66,
    top = 16,
    bottom = 24;
  const values = points.flatMap((p) => [p.stock_index, p.benchmark_index]);
  const low = Math.min(...values),
    high = Math.max(...values),
    pad = Math.max((high - low) * 0.12, 1),
    min = low - pad,
    max = high + pad;
  const x = (i: number) =>
    left + (i / Math.max(points.length - 1, 1)) * (width - left - right);
  const y = (v: number) =>
    top + ((max - v) / (max - min)) * (height - top - bottom);
  const series = [
    { key: "stock_index" as const, label: symbol, color: "var(--amber)" },
    { key: "benchmark_index" as const, label: "Peers", color: "var(--cyan)" },
  ];
  const active = points[cursor ?? points.length - 1];
  return (
    <TerminalPanel title="Indexed performance" meta={`${symbol} / Peers`}>
      <div className="chart-readout">
        {active.trade_date} / {symbol} {active.stock_index.toFixed(2)} / Peers{" "}
        {active.benchmark_index.toFixed(2)}
      </div>
      <svg
        className="comparison-chart"
        role="img"
        aria-label={`${symbol} indexed performance versus industry peers`}
        viewBox={`0 0 ${width} ${height}`}
        tabIndex={0}
        onPointerMove={(e) => {
          const b = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - b.left) / b.width) * width;
          setCursor(
            Math.max(
              0,
              Math.min(
                points.length - 1,
                Math.round(
                  ((px - left) / (width - left - right)) * (points.length - 1),
                ),
              ),
            ),
          );
        }}
        onPointerLeave={() => setCursor(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
            e.preventDefault();
            setCursor(
              Math.max(
                0,
                Math.min(
                  points.length - 1,
                  (cursor ?? points.length - 1) +
                    (e.key === "ArrowLeft" ? -1 : 1),
                ),
              ),
            );
          }
        }}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((r) => (
          <g key={r}>
            <line
              className="chart-grid"
              x1={left}
              x2={width - right}
              y1={y(max - r * (max - min))}
              y2={y(max - r * (max - min))}
            />
            <text
              x={left - 6}
              y={y(max - r * (max - min)) + 4}
              textAnchor="end"
            >
              {(max - r * (max - min)).toFixed(1)}
            </text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.key}>
            <polyline
              points={points.map((p, i) => `${x(i)},${y(p[s.key])}`).join(" ")}
              fill="none"
              stroke={s.color}
            />
            <rect
              x={width - right}
              y={y(points.at(-1)![s.key]) - 8}
              width={right}
              height={16}
              fill={s.color}
            />
            <text
              className="chart-tag"
              x={width - 4}
              y={y(points.at(-1)![s.key]) + 4}
              textAnchor="end"
            >
              {points.at(-1)![s.key].toFixed(2)}
            </text>
          </g>
        ))}
        {cursor !== null && (
          <g className="chart-crosshair">
            <line x1={x(cursor)} x2={x(cursor)} y1={top} y2={height - bottom} />
            <line
              x1={left}
              x2={width - right}
              y1={y(active.stock_index)}
              y2={y(active.stock_index)}
            />
          </g>
        )}
        <text x={left} y={height - 4}>
          {points[0].trade_date}
        </text>
        <text x={width - right} y={height - 4} textAnchor="end">
          {points.at(-1)!.trade_date}
        </text>
      </svg>
    </TerminalPanel>
  );
}
