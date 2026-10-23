import { Box, Stack, Typography } from "@mui/material";

import type { ComparisonPoint } from "./types";

interface Props { points: ComparisonPoint[]; symbol: string }

export default function ComparisonChart({ points, symbol }: Props) {
  const width = 900; const height = 330; const left = 54; const right = 18; const top = 20; const bottom = 42;
  const values = points.flatMap((point) => [point.stock_index, point.benchmark_index]);
  const rawMin = Math.min(...values); const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.12, 1);
  const min = rawMin - padding; const max = rawMax + padding;
  const x = (index: number) => left + (index / Math.max(points.length - 1, 1)) * (width - left - right);
  const y = (value: number) => top + ((max - value) / (max - min)) * (height - top - bottom);
  const line = (key: "stock_index" | "benchmark_index") => points.map((point, index) => `${x(index)},${y(point[key])}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({ value: max - ratio * (max - min), y: top + ratio * (height - top - bottom) }));

  return (
    <Box sx={{ overflowX: "auto" }}>
      <Stack direction="row" spacing={3} sx={{ mb: 1 }}>
        <Typography variant="body2" sx={{ color: "#046A38", fontWeight: 700 }}>
          ━ {symbol}
        </Typography>
        <Typography variant="body2" sx={{ color: "#3F5B7A", fontWeight: 700 }}>
          ━ Peer benchmark
        </Typography>
      </Stack>
      <Box
        component="svg"
        role="img"
        aria-label={`${symbol} indexed performance versus industry peers`}
        viewBox={`0 0 ${width} ${height}`}
        sx={{ width: "100%", minWidth: 600, height: "auto", display: "block" }}
      >
        {ticks.map((tick) => (
          <g key={tick.y}>
            <line x1={left} x2={width - right} y1={tick.y} y2={tick.y} stroke="rgba(41,45,42,0.12)" strokeDasharray="3 3" />
            <text x={left - 8} y={tick.y + 4} textAnchor="end" fontSize="14" fontWeight="500" fill="#686B64" fontFamily="JetBrains Mono, monospace">
              {tick.value.toFixed(0)}
            </text>
          </g>
        ))}
        <polyline points={line("benchmark_index")} fill="none" stroke="#3F5B7A" strokeWidth="2.5" />
        <polyline points={line("stock_index")} fill="none" stroke="#046A38" strokeWidth="3" />
        <text x={left} y={height - 12} fontSize="14" fontWeight="500" fill="#686B64" fontFamily="Inter, sans-serif">
          {points[0]?.trade_date}
        </text>
        <text x={width - right} y={height - 12} textAnchor="end" fontSize="14" fontWeight="500" fill="#686B64" fontFamily="Inter, sans-serif">
          {points.at(-1)?.trade_date}
        </text>
      </Box>
    </Box>
  );
}
