import React, { useState } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  FormControl,
  FormControlLabel,
  FormLabel,
  InputLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import Grid from "@mui/material/Grid";
import { useForm, Controller, useWatch } from "react-hook-form";
import { z } from "zod";
import { useMutation } from "@tanstack/react-query";
import { postJson, useApi } from "./api";
import type { Portfolio, ShockRequest, ShockScenarioResponse } from "./types";

const shockSchema = z.object({
  portfolioId: z.string().min(1, "Please select a portfolio"),
  symbol: z.string().min(1, "Please select an asset to shock"),
  shockPct: z
    .number()
    .min(-50, "Shock cannot be lower than -50%")
    .max(50, "Shock cannot exceed +50%"),
  method: z.enum(["regression_beta", "mst_path_decay"]),
});

type ShockFormValues = z.infer<typeof shockSchema>;

export default function ShockPage(): React.ReactElement {
  const [formError, setFormError] = useState<string | null>(null);

  // Load user portfolios
  const { data: portfolios = [], isLoading: isLoadingPortfolios } =
    useApi<Portfolio[]>("/portfolios");

  // React Hook Form
  const {
    control,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ShockFormValues>({
    defaultValues: {
      portfolioId: "",
      symbol: "",
      shockPct: -10,
      method: "regression_beta",
    },
  });

  const portfolioList = Array.isArray(portfolios) ? portfolios : [];
  const currentPortfolioId = useWatch({ control, name: "portfolioId" });
  const selectedPortfolio = portfolioList.find((p) => p.id === currentPortfolioId);

  // Shock mutation
  const shockMutation = useMutation<ShockScenarioResponse, Error, ShockFormValues>({
    mutationFn: (values) =>
      postJson<ShockScenarioResponse, ShockRequest>(
        `/portfolios/${values.portfolioId}/shocks`,
        {
          symbol: values.symbol,
          shock_pct: values.shockPct,
          method: values.method,
        }
      ),
  });

  const onSubmit = (values: ShockFormValues) => {
    setFormError(null);
    const parsed = shockSchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? "Invalid form input");
      return;
    }
    shockMutation.mutate(parsed.data);
  };


  const scenario = shockMutation.data;

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Page Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: "#0f172a" }}>
          Shock & Scenario Simulation
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Simulate hypothetical asset shocks and stress propagation through pairwise
          regression beta or Minimum Spanning Tree correlation paths.
        </Typography>
      </Box>

      {/* Mandatory Scenario Banner */}
      <Alert severity="warning" sx={{ mb: 4, borderRadius: 2 }}>
        <AlertTitle sx={{ fontWeight: 700 }}>
          Scenario estimate, not a prediction
        </AlertTitle>
        Hypothetical stress scenarios model historical co-movement and statistical
        sensitivities. They do not constitute forward price forecasts, guarantees, or
        investment advice.
      </Alert>

      {/* Shock Simulation Form */}
      <Card variant="outlined" sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" sx={{ fontSize: "1.1rem", fontWeight: 600, mb: 2 }}>
            Configure Stress Scenario
          </Typography>

          {(formError || shockMutation.error) && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError || shockMutation.error?.message}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit(onSubmit)}>
            <Grid container spacing={3}>
              {/* Portfolio Select */}
              <Grid size={{ xs: 12, md: 4 }}>
                <FormControl fullWidth size="small" error={Boolean(errors.portfolioId)}>
                  <InputLabel id="portfolio-select-label">Select Portfolio</InputLabel>
                  <Controller
                    name="portfolioId"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        labelId="portfolio-select-label"
                        label="Select Portfolio"
                        disabled={isLoadingPortfolios}
                        onChange={(e) => {
                          field.onChange(e);
                          setValue("symbol", ""); // Reset symbol on portfolio switch
                        }}

                      >
                        {portfolioList.map((p) => (
                          <MenuItem key={p.id} value={p.id}>
                            {p.name} ({p.holdings.length} holdings)
                          </MenuItem>
                        ))}
                      </Select>
                    )}
                  />
                  {errors.portfolioId && (
                    <Typography variant="caption" color="error">
                      {errors.portfolioId.message}
                    </Typography>
                  )}
                </FormControl>
              </Grid>

              {/* Asset to Shock Select */}
              <Grid size={{ xs: 12, md: 4 }}>
                <FormControl fullWidth size="small" error={Boolean(errors.symbol)}>
                  <InputLabel id="asset-select-label">Asset to Shock</InputLabel>
                  <Controller
                    name="symbol"
                    control={control}
                    render={({ field }) => (
                      <Select
                        {...field}
                        labelId="asset-select-label"
                        label="Asset to Shock"
                        disabled={!selectedPortfolio || selectedPortfolio.holdings.length === 0}
                      >
                        {selectedPortfolio?.holdings.map((h) => (
                          <MenuItem key={h.symbol} value={h.symbol}>
                            {h.symbol} ({(h.weight * 100).toFixed(1)}% weight)
                          </MenuItem>
                        ))}
                      </Select>
                    )}
                  />
                  {errors.symbol && (
                    <Typography variant="caption" color="error">
                      {errors.symbol.message}
                    </Typography>
                  )}
                </FormControl>
              </Grid>

              {/* Shock Percentage Input */}
              <Grid size={{ xs: 12, md: 4 }}>
                <Controller
                  name="shockPct"
                  control={control}
                  render={({ field }) => (
                    <TextField
                      {...field}
                      fullWidth
                      size="small"
                      type="number"
                      label="Hypothetical Shock (%)"
                      error={Boolean(errors.shockPct)}
                      helperText={errors.shockPct?.message ?? "Permitted range: -50% to +50%"}
                      onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                    />
                  )}
                />
              </Grid>

              {/* Propagation Method Selection */}
              <Grid size={{ xs: 12 }}>
                <FormControl component="fieldset">
                  <FormLabel component="legend" sx={{ fontSize: "0.875rem", fontWeight: 600 }}>
                    Propagation Mechanism (SRS OQ-6)
                  </FormLabel>
                  <Controller
                    name="method"
                    control={control}
                    render={({ field }) => (
                      <RadioGroup row {...field}>
                        <FormControlLabel
                          value="regression_beta"
                          control={<Radio size="small" />}
                          label="Pairwise Regression Beta (Default: Cov(r_j, r_s) / Var(r_s))"
                        />
                        <FormControlLabel
                          value="mst_path_decay"
                          control={<Radio size="small" />}
                          label="MST-Path Decay (Graph product of tree correlations)"
                        />
                      </RadioGroup>
                    )}
                  />
                </FormControl>
              </Grid>

              {/* Submit Button */}
              <Grid size={{ xs: 12 }}>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={shockMutation.isPending || !selectedPortfolio}
                  startIcon={
                    shockMutation.isPending ? (
                      <CircularProgress size={18} color="inherit" />
                    ) : null
                  }
                >
                  Run Shock Simulation
                </Button>
              </Grid>
            </Grid>
          </Box>
        </CardContent>
      </Card>

      {/* Error state */}
      {shockMutation.isError && (
        <Alert severity="error" sx={{ mb: 4 }}>
          {shockMutation.error?.message || "Failed to execute shock simulation."}
        </Alert>
      )}

      {/* Scenario Results */}
      {scenario && (
        <Box sx={{ mb: 4 }}>
          {/* Headline Metric Card */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid size={{ xs: 12, md: 4 }}>
              <Card
                variant="outlined"
                sx={{
                  borderTop: `4px solid ${scenario.portfolio_impact_pct < 0 ? "#dc2626" : "#16a34a"
                    }`,
                }}
              >
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Estimated Portfolio Impact
                  </Typography>
                  <Typography
                    variant="h4"
                    sx={{
                      fontWeight: 700,
                      my: 1,
                      color: scenario.portfolio_impact_pct < 0 ? "#dc2626" : "#16a34a",
                    }}
                  >
                    {scenario.portfolio_impact_pct > 0 ? "+" : ""}
                    {scenario.portfolio_impact_pct.toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Aggregate portfolio loss under {scenario.shock_pct}% shock to{" "}
                    {scenario.shocked_symbol}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Shocked Security
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, my: 1, color: "#0f172a" }}>
                    {scenario.shocked_symbol}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Direct shock applied: {scenario.shock_pct.toFixed(1)}%
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Simulation Engine
                  </Typography>
                  <Typography variant="h6" sx={{ fontWeight: 600, my: 1, color: "#0f172a" }}>
                    {scenario.method_version}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Banner: &quot;{scenario.banner}&quot;
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Results Table */}
          <Card variant="outlined" sx={{ mb: 4 }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontSize: "1rem", fontWeight: 600, mb: 2 }}>
                Holding Impact & Loss Contribution Breakdown
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: "#f8fafc" }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Holding</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Capital Weight</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Sensitivity (Beta/Decay)</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Estimated Asset Impact</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Portfolio Contribution</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {scenario.results.map((row) => {
                      const isShocked = row.symbol === scenario.shocked_symbol;
                      const sensitivity = row.method_detail.sensitivity ?? 0;
                      return (
                        <TableRow
                          key={row.symbol}
                          sx={{
                            bgcolor: isShocked ? "#fef3c7" : "inherit",
                            "&:hover": { bgcolor: "#f1f5f9" },
                          }}
                        >
                          <TableCell sx={{ fontWeight: isShocked ? 700 : 500 }}>
                            {row.symbol} {isShocked && "(Shock Source)"}
                          </TableCell>
                          <TableCell align="right">{(row.weight * 100).toFixed(1)}%</TableCell>
                          <TableCell align="right">{sensitivity.toFixed(2)}</TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              fontWeight: 600,
                              color: row.estimated_impact_pct < 0 ? "#dc2626" : "#16a34a",
                            }}
                          >
                            {row.estimated_impact_pct > 0 ? "+" : ""}
                            {row.estimated_impact_pct.toFixed(2)}%
                          </TableCell>
                          <TableCell
                            align="right"
                            sx={{
                              fontWeight: 700,
                              color: row.contribution_pct < 0 ? "#dc2626" : "#16a34a",
                            }}
                          >
                            {row.contribution_pct > 0 ? "+" : ""}
                            {row.contribution_pct.toFixed(2)}%
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          {/* Modeling Assumptions Panel */}
          <Card variant="outlined" sx={{ bgcolor: "#fafafa" }}>
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                Model Assumptions & Boundaries (SRS FR-I2)
              </Typography>
              <Stack spacing={0.75}>
                {scenario.assumptions.map((asm, idx) => (
                  <Typography key={idx} variant="body2" color="text.secondary">
                    &bull; {asm}
                  </Typography>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Box>
      )}
    </Container>
  );
}
