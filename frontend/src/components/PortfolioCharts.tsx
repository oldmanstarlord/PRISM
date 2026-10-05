import { Suspense, lazy } from "react";
import { Box, Card, CardContent, CircularProgress, Typography } from "@mui/material";
import type { DrawdownPoint, RiskContribution } from "../types";

// Lazy load react-plotly.js to reduce initial bundle and prevent test runner issues
const Plot = lazy(() => import("react-plotly.js"));

interface RiskContributionChartProps {
  contributions: RiskContribution[];
}

interface DrawdownChartProps {
  drawdownSeries: DrawdownPoint[];
}

function ChartFallback() {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: 320,
        backgroundColor: "#f8fafc",
        borderRadius: 1,
      }}
    >
      <CircularProgress size={28} />
    </Box>
  );
}

export function RiskContributionChart({ contributions }: RiskContributionChartProps) {
  if (!contributions || contributions.length === 0) {
    return null;
  }

  const symbols = contributions.map((c) => c.symbol);
  const weightsPct = contributions.map((c) => Number((c.weight * 100).toFixed(2)));
  const prcPct = contributions.map((c) => Number((c.percent_contribution * 100).toFixed(2)));

  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="h6" sx={{ fontSize: "1rem", fontWeight: 600, mb: 1 }}>
          Euler Risk Contribution Decomposition
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Comparing capital weight vs percentage risk contribution (PRC) to overall volatility.
        </Typography>
        <Suspense fallback={<ChartFallback />}>
          <Box sx={{ width: "100%", height: 320 }}>
            <Plot
              data={[
                {
                  x: symbols,
                  y: weightsPct,
                  name: "Capital Weight (%)",
                  type: "bar",
                  marker: { color: "#64748b" },
                },
                {
                  x: symbols,
                  y: prcPct,
                  name: "Risk Contribution (%)",
                  type: "bar",
                  marker: { color: "#0284c7" },
                },
              ]}
              layout={{
                barmode: "group",
                autosize: true,
                margin: { l: 40, r: 20, t: 20, b: 40 },
                legend: { orientation: "h", y: 1.15 },
                paper_bgcolor: "transparent",
                plot_bgcolor: "transparent",
                yaxis: { title: { text: "Percentage (%)" } },
              }}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
              config={{ displayModeBar: false }}
            />
          </Box>
        </Suspense>
      </CardContent>
    </Card>
  );
}

export function DrawdownChart({ drawdownSeries }: DrawdownChartProps) {
  if (!drawdownSeries || drawdownSeries.length === 0) {
    return null;
  }

  const dates = drawdownSeries.map((d) => d.date);
  const drawdownsPct = drawdownSeries.map((d) => Number((d.drawdown * 100).toFixed(2)));

  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="h6" sx={{ fontSize: "1rem", fontWeight: 600, mb: 1 }}>
          Historical Drawdown Profile
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Cumulative percentage drop from historical high watermark (buy-and-hold).
        </Typography>
        <Suspense fallback={<ChartFallback />}>
          <Box sx={{ width: "100%", height: 320 }}>
            <Plot
              data={[
                {
                  x: dates,
                  y: drawdownsPct,
                  name: "Drawdown (%)",
                  type: "scatter",
                  mode: "lines",
                  fill: "tozeroy",
                  line: { color: "#dc2626", width: 2 },
                  fillcolor: "rgba(220, 38, 38, 0.12)",
                },
              ]}
              layout={{
                autosize: true,
                margin: { l: 40, r: 20, t: 20, b: 40 },
                paper_bgcolor: "transparent",
                plot_bgcolor: "transparent",
                yaxis: {
                  title: { text: "Drawdown (%)" },
                  zeroline: true,
                  zerolinecolor: "#94a3b8",
                },
                xaxis: { showgrid: false },
              }}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
              config={{ displayModeBar: false }}
            />
          </Box>
        </Suspense>
      </CardContent>
    </Card>
  );
}
