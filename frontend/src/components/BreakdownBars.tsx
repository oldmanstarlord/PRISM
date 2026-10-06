import {
  Box,
  Button,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import type { BreakdownItem } from "../types";
import { StatusChip } from "./StatusChip";

export interface BreakdownBarsProps {
  items: BreakdownItem[];
  title?: string;
  showDimensions?: boolean;
  onExplain?: (item: BreakdownItem) => void;
}

export function BreakdownBars({
  items,
  title = "Component Breakdown & Point Contributions",
  showDimensions = true,
  onExplain,
}: BreakdownBarsProps) {
  if (!items || items.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
        <Typography color="text.secondary">No component breakdown available.</Typography>
      </Paper>
    );
  }

  // Calculate totals if points/weights available
  const totalPoints = items.reduce((acc, it) => acc + (it.risk_points ?? 0), 0);
  const totalWeight = items.reduce((acc, it) => acc + (it.weight ?? 0), 0);

  return (
    <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        sx={{ justifyContent: "space-between", alignItems: { sm: "center" }, mb: 2 }}
      >
        <Typography variant="h6" sx={{ fontWeight: 650 }}>
          {title}
        </Typography>
        {totalWeight > 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
            Total Contribution: {totalPoints.toFixed(1)} pts / {totalWeight.toFixed(0)} wt
          </Typography>
        )}
      </Stack>

      <TableContainer>
        <Table size="small" aria-label="risk component breakdown table">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 700 }}>Component</TableCell>
              {showDimensions && <TableCell sx={{ fontWeight: 700 }}>Dimension</TableCell>}
              <TableCell sx={{ fontWeight: 700, minWidth: 160 }}>Percentile Rank</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Points</TableCell>
              <TableCell align="right" sx={{ fontWeight: 700 }}>Weight</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
              <TableCell sx={{ fontWeight: 700 }}>Driver Reason</TableCell>
              {onExplain && <TableCell sx={{ fontWeight: 700 }}>Explanation</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {items.map((item) => {
              const pct = item.percentile !== undefined ? Math.min(100, Math.max(0, item.percentile)) : undefined;

              return (
                <TableRow key={item.key} hover>
                  <TableCell sx={{ fontWeight: 600 }}>
                    {item.display_name}
                    {item.data_age_days !== undefined && item.data_age_days > 1 && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                        Age: {item.data_age_days}d
                      </Typography>
                    )}
                  </TableCell>

                  {showDimensions && (
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {item.dimension ?? "General"}
                      </Typography>
                    </TableCell>
                  )}

                  <TableCell>
                    {pct !== undefined ? (
                      <Tooltip title={`${pct.toFixed(1)}th percentile`} arrow>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <Box sx={{ width: "100%", mr: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={pct}
                              sx={{
                                height: 8,
                                borderRadius: 4,
                                bgcolor: "#e2e8f0",
                                "& .MuiLinearProgress-bar": {
                                  bgcolor: pct >= 80 ? "error.main" : pct >= 50 ? "warning.main" : "primary.main",
                                },
                              }}
                            />
                          </Box>
                          <Typography variant="body2" sx={{ minWidth: 35, fontVariantNumeric: "tabular-nums" }}>
                            {pct.toFixed(0)}%
                          </Typography>
                        </Box>
                      </Tooltip>
                    ) : (
                      <Typography variant="caption" color="text.secondary">N/A</Typography>
                    )}
                  </TableCell>

                  <TableCell align="right" sx={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
                    {item.risk_points !== undefined ? item.risk_points.toFixed(1) : "—"}
                  </TableCell>

                  <TableCell align="right" sx={{ color: "text.secondary", fontVariantNumeric: "tabular-nums" }}>
                    {item.weight !== undefined ? item.weight.toFixed(0) : "—"}
                  </TableCell>

                  <TableCell>
                    <StatusChip status={item.status ?? "active"} />
                  </TableCell>

                  <TableCell sx={{ maxWidth: 280 }}>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                      {item.reason ?? "No anomalies detected."}
                    </Typography>
                  </TableCell>
                  {onExplain && (
                    <TableCell>
                      <Button size="small" onClick={() => onExplain(item)} aria-label={`Why ${item.display_name}?`}>
                        Why?
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
