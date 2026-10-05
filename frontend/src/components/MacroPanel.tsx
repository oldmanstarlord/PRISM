import React from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import PublicIcon from "@mui/icons-material/Public";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { useApi } from "../api";
import type { StockMacroExposure } from "../types";

interface MacroPanelProps {
  symbol: string;
}

export function MacroPanel({ symbol }: MacroPanelProps): React.ReactElement {
  const { data, isLoading, error } = useApi<StockMacroExposure>(
    `/stocks/${encodeURIComponent(symbol)}/macro`
  );

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error || !data || !data.regime || !Array.isArray(data.sensitivities)) {
    return (
      <Alert severity="info" sx={{ mb: 3 }}>
        Macro sensitivity data not yet available for {symbol}.
      </Alert>
    );
  }

  const { regime, regime_multiplier = 1.0, sensitivities, recent_shocks = {}, limitations = [] } = data;

  return (
    <Card variant="outlined" sx={{ mb: 3, borderRadius: 2, bgcolor: "#ffffff" }}>
      <CardContent sx={{ p: 3 }}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={2}
          sx={{
            mb: 2.5,
            justifyContent: "space-between",
            alignItems: { xs: "flex-start", sm: "center" },
          }}
        >
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
            <PublicIcon color="primary" />
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Macroeconomic Factor Sensitivity (Dimension: Macro)
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Sector-level co-movement ({data.industry}) scaled by prevailing market regime.
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Chip
              label={`REGIME: ${regime.toUpperCase()}`}
              color={
                regime === "stressed" ? "error" : regime === "trending" ? "warning" : "success"
              }
              sx={{ fontWeight: 800 }}
            />
            <Chip
              label={`Multiplier: ${regime_multiplier.toFixed(2)}x`}
              variant="outlined"
              sx={{ fontWeight: 700 }}
            />
          </Stack>
        </Stack>

        {/* Summary Metric Cards */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 4 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                SECTOR INDUSTRY
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5 }}>
                {data.industry}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Peer benchmark exposure group
              </Typography>
            </Paper>
          </Grid>

          <Grid size={{ xs: 12, sm: 4 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                SIGNIFICANT MACRO DRIVERS
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5, color: "primary.main" }}>
                {sensitivities.filter((s) => s.is_significant).length} of {sensitivities.length}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Drivers passing |t| ≥ 1.96 threshold
              </Typography>
            </Paper>
          </Grid>

          <Grid size={{ xs: 12, sm: 4 }}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "#f8fafc" }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                MACRO RAW EXPOSURE SCORE
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 800, mt: 0.5, color: "warning.dark" }}>
                {data.macro_score !== null ? data.macro_score.toFixed(2) : "0.00"} pts
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ∑ (|β| × |z|) × Regime Multiplier
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Sensitivities Table */}
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
          Factor Sensitivity Decomposition & Recent Moves
        </Typography>
        <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, mb: 2 }}>
          <Table size="small">
            <TableHead sx={{ bgcolor: "#f8fafc" }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Macro Factor</TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  Sector Beta (β)
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  t-Statistic
                </TableCell>
                <TableCell align="center" sx={{ fontWeight: 700 }}>
                  Significance
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  21-Day Move
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 700 }}>
                  Recent Z-Score
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sensitivities.map((s) => {
                const shock = recent_shocks[s.series_key];
                return (
                  <TableRow
                    key={s.series_key}
                    hover
                    sx={{
                      bgcolor: s.is_significant ? "rgba(2, 132, 199, 0.04)" : "inherit",
                    }}
                  >
                    <TableCell sx={{ fontWeight: 600 }}>
                      {s.series_name || s.series_key}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontWeight: 700,
                        color:
                          s.beta > 0
                            ? "success.main"
                            : s.beta < 0
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {s.beta > 0 ? `+${s.beta.toFixed(4)}` : s.beta.toFixed(4)}
                    </TableCell>
                    <TableCell align="right">{s.t_stat.toFixed(2)}</TableCell>
                    <TableCell align="center">
                      <Chip
                        size="small"
                        label={s.is_significant ? "Significant" : "Insignificant"}
                        color={s.is_significant ? "primary" : "default"}
                        variant={s.is_significant ? "filled" : "outlined"}
                        sx={{ height: 20, fontSize: "0.7rem", fontWeight: 700 }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      {shock
                        ? shock.move_21d > 0
                          ? `+${(shock.move_21d * 100).toFixed(2)}%`
                          : `${(shock.move_21d * 100).toFixed(2)}%`
                        : "—"}
                    </TableCell>
                    <TableCell align="right" sx={{ fontWeight: 600 }}>
                      {shock ? shock.z_score.toFixed(2) : "—"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Limitations & Explanations */}
        {limitations && limitations.length > 0 && (
          <Alert severity="info" icon={<InfoOutlinedIcon />} sx={{ borderRadius: 2 }}>
            <Typography variant="caption" sx={{ display: "block", fontWeight: 600 }}>
              Methodology & Limitations (D3):
            </Typography>
            {limitations.map((lim, idx) => (
              <Typography key={idx} variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                • {lim}
              </Typography>
            ))}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
