import React, { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  FormControlLabel,
  Grid,
  MenuItem,
  Paper,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { z } from "zod";
import { useApi, apiBase, fetchJson, postJson } from "./api";
import { ExplainPanel } from "./components/ExplainPanel";
import { FreshnessBadge } from "./components/FreshnessBadge";
import { DrawdownChart, RiskContributionChart } from "./components/PortfolioCharts";
import type {
  DiversificationResponse,
  Portfolio,
  PortfolioRiskScore,
  PortfolioRiskRun,
  PortfolioImportResult,
  RowValidationError,
} from "./types";

const manualHoldingSchema = z.object({
  symbol: z.string().min(1, "Symbol is required"),
  weight: z.number().min(0).max(1).optional(),
  quantity: z.number().min(0).optional(),
});

const manualPortfolioSchema = z.object({
  name: z.string().min(1, "Portfolio name is required"),
  description: z.string().optional(),
  holdings: z.array(manualHoldingSchema).min(1, "At least one holding is required"),
});

type ManualPortfolioForm = z.infer<typeof manualPortfolioSchema>;

export default function PortfolioPage() {
  const [activeTab, setActiveTab] = useState<number>(0);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvText, setCsvText] = useState<string>("");
  const [csvName, setCsvName] = useState<string>("My CSV Portfolio");
  const [validationErrors, setValidationErrors] = useState<RowValidationError[]>([]);
  const [actionWarning, setActionWarning] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [riskData, setRiskData] = useState<PortfolioRiskRun | null>(null);
  const [riskScore, setRiskScore] = useState<PortfolioRiskScore | null>(null);
  const [divData, setDivData] = useState<DiversificationResponse | null>(null);
  const [isLoadingDiv, setIsLoadingDiv] = useState<boolean>(false);
  const [forceRerun, setForceRerun] = useState<boolean>(false);


  // Load existing portfolios
  const {
    data: portfolios,
    isLoading: loadingPortfolios,
    refetch: refetchPortfolios,
  } = useApi<Portfolio[]>("/portfolios");

  // React Hook Form for manual entry
  const {
    control,
    handleSubmit,
    formState: { errors: formErrors },
  } = useForm<ManualPortfolioForm>({
    defaultValues: {
      name: "New Portfolio",
      description: "Direct asset allocation",
      holdings: [
        { symbol: "INFY", weight: 0.5 },
        { symbol: "TCS", weight: 0.5 },
      ],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "holdings",
  });

  // Calculate or fetch risk for a portfolio
  const fetchRiskRun = async (portfolioId: string, force: boolean = false) => {
    setIsSubmitting(true);
    setActionWarning(null);
    try {
      const response = await fetch(`${apiBase}/portfolios/${portfolioId}/risk-runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force_rerun: force }),
      });
      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson.detail ?? "Failed to compute risk run");
      }
      const data: PortfolioRiskRun = await response.json();
      setRiskData(data);

      try {
        setRiskScore(
          await fetchJson<PortfolioRiskScore>(`/portfolios/${portfolioId}/risk-score/latest`)
        );
      } catch {
        setRiskScore(null);
      }

      // Fetch diversification metrics
      setIsLoadingDiv(true);
      try {
        const divRes = await postJson<DiversificationResponse>(
          `/portfolios/${portfolioId}/diversification`
        );
        setDivData(divRes);
      } catch {
        // Non-blocking diversification load failure
      } finally {
        setIsLoadingDiv(false);
      }
    } catch (err: unknown) {
      setActionWarning(err instanceof Error ? err.message : "Error executing risk calculation");
    } finally {
      setIsSubmitting(false);
    }

  };

  // Submit manual portfolio
  const onManualSubmit = async (formData: ManualPortfolioForm) => {
    setIsSubmitting(true);
    setValidationErrors([]);
    setActionWarning(null);

    // Validate with zod
    const parsed = manualPortfolioSchema.safeParse(formData);
    if (!parsed.success) {
      setActionWarning(parsed.error.issues.map((i) => i.message).join(", "));
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch(`${apiBase}/portfolios`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          holdings: formData.holdings,
        }),
      });

      if (!response.ok) {
        const errData = await response.json();
        if (errData.detail?.errors) {
          setValidationErrors(errData.detail.errors);
        } else {
          setActionWarning(errData.detail ?? "Failed to create portfolio");
        }
        setIsSubmitting(false);
        return;
      }

      const created: Portfolio = await response.json();
      setSelectedPortfolioId(created.id);
      await refetchPortfolios();
      await fetchRiskRun(created.id, false);
    } catch (err: unknown) {
      setActionWarning(err instanceof Error ? err.message : "Error creating portfolio");
      setIsSubmitting(false);
    }
  };

  // Submit CSV upload
  const onCsvSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setValidationErrors([]);
    setActionWarning(null);

    const formData = new FormData();
    formData.append("name", csvName);
    if (csvFile) {
      formData.append("file", csvFile);
    } else if (csvText.trim()) {
      formData.append("csv_text", csvText);
    } else {
      setValidationErrors([{ row: 1, error: "Please select a CSV file or paste CSV content." }]);
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch(`${apiBase}/portfolios/import-csv`, {
        method: "POST",
        body: formData,
      });

      const result: PortfolioImportResult = await response.json();

      if (result.errors && result.errors.length > 0) {
        setValidationErrors(result.errors);
        if (result.warnings && result.warnings.length > 0) {
          setActionWarning(result.warnings.join("; "));
        }
        setIsSubmitting(false);
        return;
      }

      if (result.portfolio) {
        setSelectedPortfolioId(result.portfolio.id);
        await refetchPortfolios();
        await fetchRiskRun(result.portfolio.id, false);
      }
    } catch (err: unknown) {
      setActionWarning(err instanceof Error ? err.message : "Failed to import CSV portfolio");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        sx={{
          mb: 3,
          justifyContent: "space-between",
          alignItems: { xs: "flex-start", sm: "center" },
        }}
      >
        <Box>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "#0f172a" }}>
            Portfolio Risk & Holdings
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Position valuation, Ledoit-Wolf covariance shrinkage, Euler risk decomposition, and VaR/ES.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
          <FreshnessBadge
            asOf={riskData?.as_of ?? new Date().toISOString().slice(0, 10)}
            label="Risk Engine Cutoff"
          />
          <Chip label="FR-P1 / FR-R1-R7" size="small" variant="outlined" color="primary" />
        </Stack>
      </Stack>

      {/* Portfolio Selector / Switcher */}
      <Paper variant="outlined" sx={{ p: 2, mb: 4, bgcolor: "#f8fafc" }}>
        <Grid container spacing={2} sx={{ alignItems: "center" }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TextField
              select
              fullWidth
              size="small"
              label="Select Existing Portfolio"
              value={selectedPortfolioId}
              onChange={(e) => {
                const id = e.target.value;
                setSelectedPortfolioId(id);
                if (id) {
                  fetchRiskRun(id, forceRerun);
                }
              }}
              disabled={loadingPortfolios || !portfolios || portfolios.length === 0}
            >
              {portfolios && portfolios.length > 0 ? (
                portfolios.map((p) => (
                  <MenuItem key={p.id} value={p.id}>
                    {p.name} ({p.holdings.length} holdings) &mdash; {p.created_at.slice(0, 10)}
                  </MenuItem>
                ))
              ) : (
                <MenuItem value="">No portfolios saved yet</MenuItem>
              )}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Stack
              direction="row"
              spacing={2}
              sx={{ alignItems: "center", justifyContent: "flex-end" }}
            >
              <FormControlLabel
                control={
                  <Switch
                    checked={forceRerun}
                    onChange={(e) => setForceRerun(e.target.checked)}
                    size="small"
                  />
                }
                label="Force Rerun (Bypass Cache)"
              />
              <Button
                variant="contained"
                onClick={() => selectedPortfolioId && fetchRiskRun(selectedPortfolioId, forceRerun)}
                disabled={!selectedPortfolioId || isSubmitting}
                startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : null}
              >
                Compute Risk
              </Button>
            </Stack>
          </Grid>
        </Grid>
      </Paper>

      {/* Input Section: Tabs for Manual vs CSV */}
      <Card variant="outlined" sx={{ mb: 4 }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          sx={{ borderBottom: 1, borderColor: "divider", px: 2 }}
        >
          <Tab label="Manual Holdings Form" id="portfolio-tab-manual" />
          <Tab label="CSV Upload & Import" id="portfolio-tab-csv" />
        </Tabs>

        <CardContent sx={{ p: 3 }}>
          {/* Tab 0: Manual Entry Form */}
          {activeTab === 0 && (
            <Box component="form" onSubmit={handleSubmit(onManualSubmit)}>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Controller
                    name="name"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        fullWidth
                        size="small"
                        label="Portfolio Name"
                        error={Boolean(formErrors.name)}
                        helperText={formErrors.name?.message}
                      />
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <Controller
                    name="description"
                    control={control}
                    render={({ field }) => (
                      <TextField
                        {...field}
                        fullWidth
                        size="small"
                        label="Description (Optional)"
                      />
                    )}
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5 }}>
                    Asset Positions (Weights normalize strictly to 1.0; residual to CASH)
                  </Typography>

                  <Stack spacing={1.5}>
                    {fields.map((fieldItem, index) => (
                      <Stack
                        key={fieldItem.id}
                        direction="row"
                        spacing={2}
                        sx={{ alignItems: "center" }}
                      >
                        <Controller
                          name={`holdings.${index}.symbol`}
                          control={control}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              size="small"
                              label="Symbol / Ticker"
                              placeholder="e.g. INFY, TCS, CASH"
                              sx={{ flex: 2 }}
                              error={Boolean(formErrors.holdings?.[index]?.symbol)}
                            />
                          )}
                        />
                        <Controller
                          name={`holdings.${index}.weight`}
                          control={control}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              size="small"
                              label="Target Weight (0.0 to 1.0)"
                              type="number"
                              slotProps={{
                                htmlInput: { step: "0.01", min: "0", max: "1" },
                              }}
                              onChange={(e) =>
                                field.onChange(
                                  e.target.value === "" ? undefined : parseFloat(e.target.value)
                                )
                              }
                              sx={{ flex: 2 }}
                            />
                          )}
                        />
                        <Button
                          color="error"
                          onClick={() => remove(index)}
                          disabled={fields.length <= 1}
                          size="small"
                          aria-label="Remove holding row"
                        >
                          Remove
                        </Button>
                      </Stack>
                    ))}
                  </Stack>

                  <Button
                    onClick={() => append({ symbol: "", weight: 0.1 })}
                    sx={{ mt: 2 }}
                    size="small"
                  >
                    + Add Holding Row
                  </Button>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={isSubmitting}
                    startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : null}
                  >
                    Save & Compute Risk
                  </Button>
                </Grid>
              </Grid>
            </Box>
          )}

          {/* Tab 1: CSV Upload */}
          {activeTab === 1 && (
            <Box component="form" onSubmit={onCsvSubmit}>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    fullWidth
                    size="small"
                    label="Portfolio Name"
                    value={csvName}
                    onChange={(e) => setCsvName(e.target.value)}
                    required
                  />
                </Grid>

                <Grid size={{ xs: 12, sm: 6 }}>
                  <Button
                    variant="outlined"
                    component="label"
                    fullWidth
                    sx={{ height: 40 }}
                  >
                    {csvFile ? csvFile.name : "Choose CSV File (symbol, weight|qty)"}
                    <input
                      type="file"
                      hidden
                      accept=".csv,text/csv"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setCsvFile(e.target.files[0]);
                        }
                      }}
                    />
                  </Button>
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Or paste raw CSV text directly:
                  </Typography>
                  <TextField
                    multiline
                    rows={4}
                    fullWidth
                    placeholder={"symbol,weight\nINFY,0.50\nTCS,0.30\nCASH,0.20"}
                    value={csvText}
                    onChange={(e) => setCsvText(e.target.value)}
                  />
                </Grid>

                <Grid size={{ xs: 12 }}>
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={isSubmitting}
                    startIcon={isSubmitting ? <CircularProgress size={18} color="inherit" /> : null}
                  >
                    Upload & Calculate Risk
                  </Button>
                </Grid>
              </Grid>
            </Box>
          )}

          {/* Row-Level Errors Alert & Table */}
          {validationErrors.length > 0 && (
            <Box sx={{ mt: 3 }}>
              <Alert severity="error" sx={{ mb: 2 }}>
                Validation failed for {validationErrors.length} row(s). Correct the errors below:
              </Alert>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead sx={{ bgcolor: "#fee2e2" }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Row</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Symbol</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Field</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Error Details</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {validationErrors.map((err, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{err.row}</TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: "monospace", fontWeight: 600 }}>
                            {err.symbol ?? "-"}
                          </Typography>
                        </TableCell>
                        <TableCell>{err.field ?? "-"}</TableCell>
                        <TableCell sx={{ color: "#b91c1c" }}>{err.error}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {/* Warnings List */}
          {actionWarning && (
            <Alert severity="warning" sx={{ mt: 3 }}>
              {actionWarning}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Results Dashboard Section */}
      {riskData && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 2, color: "#0f172a" }}>
            Risk Analysis & Aggregation Results
          </Typography>

          {riskScore && (
            <Box sx={{ mb: 4 }}>
              <Grid container spacing={3}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card variant="outlined" sx={{ borderTop: "4px solid #dc2626", height: "100%" }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                        Portfolio Risk Score
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, my: 1 }}>
                        {riskScore.total_score.toFixed(1)} / 100
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Holding risk plus the portfolio structure term
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card variant="outlined" sx={{ borderTop: "4px solid #f59e0b", height: "100%" }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                        Holding / Structure
                      </Typography>
                      <Typography variant="h5" sx={{ fontWeight: 700, my: 1 }}>
                        {riskScore.holding_risk_score.toFixed(1)} / {riskScore.structure_score?.toFixed(1) ?? "N/A"}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Cluster {riskScore.structure_components.cluster_concentration?.toFixed(1) ?? "N/A"}
                        {" · "}Effective bets {riskScore.structure_components.effective_bets?.toFixed(1) ?? "N/A"}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card variant="outlined" sx={{ borderTop: "4px solid #2563eb", height: "100%" }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                        Portfolio Confidence
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, my: 1 }}>
                        {riskScore.confidence.toFixed(0)}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Weighted confidence, capped by the weakest large holding
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                  <Card variant="outlined" sx={{ borderTop: "4px solid #64748b", height: "100%" }}>
                    <CardContent>
                      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                        Score Coverage
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 700, my: 1 }}>
                        {(riskScore.coverage * 100).toFixed(0)}%
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {riskScore.status} · {riskScore.method_version}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
              {riskScore.missing_holdings.length > 0 && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  Missing current holding scores: {riskScore.missing_holdings.join(", ")}
                </Alert>
              )}
            </Box>
          )}

          {/* Summary Metric Cards */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {/* Card 1: Annualised Volatility */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card variant="outlined" sx={{ borderTop: "4px solid #0284c7" }}>
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Annualised Volatility
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: "#0f172a" }}>
                    {(riskData.portfolio_volatility * 100).toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    w&apos; &Sigma; w with Ledoit-Wolf shrinkage (&lambda; = {riskData.shrinkage_intensity.toFixed(4)})
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 2: Benchmark Beta */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card variant="outlined" sx={{ borderTop: "4px solid #10b981" }}>
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Benchmark Beta
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: "#0f172a" }}>
                    {riskData.portfolio_beta !== null && riskData.portfolio_beta !== undefined
                      ? riskData.portfolio_beta.toFixed(2)
                      : "N/A"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Relative to official NIFTY 200 Total Return index
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 3: Max Drawdown */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card variant="outlined" sx={{ borderTop: "4px solid #ef4444" }}>
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    Maximum Drawdown
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 700, my: 1, color: "#dc2626" }}>
                    -{(riskData.max_drawdown * 100).toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Peak-to-trough over 250d window
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            {/* Card 4: 1-Day VaR & ES */}
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card variant="outlined" sx={{ borderTop: "4px solid #8b5cf6" }}>
                <CardContent>
                  <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                    1-Day 95% VaR / ES
                  </Typography>
                  <Typography variant="h5" sx={{ fontWeight: 700, my: 1, color: "#0f172a" }}>
                    {riskData.var_parametric_95 !== null && riskData.var_parametric_95 !== undefined
                      ? `${(riskData.var_parametric_95 * 100).toFixed(2)}%`
                      : "N/A"}
                    {" / "}
                    {riskData.es_parametric_95 !== null && riskData.es_parametric_95 !== undefined
                      ? `${(riskData.es_parametric_95 * 100).toFixed(2)}%`
                      : "N/A"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Parametric (Hist VaR:{" "}
                    {riskData.var_historical_95 !== null && riskData.var_historical_95 !== undefined
                      ? `${(riskData.var_historical_95 * 100).toFixed(2)}%`
                      : "N/A"}
                    )
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Plotly Interactive Charts */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid size={{ xs: 12, md: 6 }}>
              <RiskContributionChart contributions={riskData.contributions} />
            </Grid>
            <Grid size={{ xs: 12, md: 6 }}>
              <DrawdownChart drawdownSeries={riskData.drawdown_series} />
            </Grid>
          </Grid>

          {/* Asset-Level Risk Contributions Table */}
          <Card variant="outlined" sx={{ mb: 4 }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontSize: "1rem", fontWeight: 600, mb: 2 }}>
                Holding Positions & Euler Risk Decomposition
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead sx={{ bgcolor: "#f8fafc" }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Holding</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Capital Weight</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Asset Volatility</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Marginal Contrib (MRC)</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>% Risk Contrib (PRC)</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>Benchmark Beta</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {riskData.contributions.map((c) => (
                      <TableRow key={c.symbol}>
                        <TableCell sx={{ fontWeight: 600 }}>{c.symbol}</TableCell>
                        <TableCell align="right">{(c.weight * 100).toFixed(2)}%</TableCell>
                        <TableCell align="right">{(c.asset_volatility * 100).toFixed(2)}%</TableCell>
                        <TableCell align="right">{(c.marginal_contribution * 100).toFixed(4)}%</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600, color: "#0284c7" }}>
                          {(c.percent_contribution * 100).toFixed(2)}%
                        </TableCell>
                        <TableCell align="right">
                          {c.beta !== null && c.beta !== undefined ? c.beta.toFixed(2) : "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          {/* Concentration Metrics */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            {/* Holdings Concentration */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                    Holdings Concentration
                  </Typography>
                  <Stack spacing={1}>
                    <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                      <Typography variant="body2" color="text.secondary">Holding HHI:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {riskData.concentration_metrics.holding_hhi?.toFixed(4) ?? "-"}
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                      <Typography variant="body2" color="text.secondary">Effective N (1/HHI):</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {riskData.concentration_metrics.effective_n?.toFixed(1) ?? "-"} assets
                      </Typography>
                    </Box>
                    <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                      <Typography variant="body2" color="text.secondary">Top Position Weight:</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {riskData.concentration_metrics.top_holding_weight
                          ? `${(riskData.concentration_metrics.top_holding_weight * 100).toFixed(1)}%`
                          : "-"}
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            {/* Industry Concentration */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                    Industry Allocation
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                    Industry HHI: {riskData.concentration_metrics.industry_hhi?.toFixed(4) ?? "-"}
                  </Typography>
                  <Stack spacing={0.75}>
                    {riskData.concentration_metrics.industry_weights &&
                      Object.entries(riskData.concentration_metrics.industry_weights).map(([ind, wt]) => (
                        <Box key={ind} sx={{ display: "flex", justifyContent: "space-between" }}>
                          <Typography variant="body2" color="text.secondary">{ind}:</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {(wt * 100).toFixed(1)}%
                          </Typography>
                        </Box>
                      ))}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            {/* Layer 2 MST Cluster Concentration */}
            <Grid size={{ xs: 12, md: 4 }}>
              <Card variant="outlined" sx={{ height: "100%" }}>
                <CardContent>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                    Layer 2 MST Cluster Concentration
                  </Typography>
                  {riskData.concentration_metrics.mst_clusters?.status === "available" ? (
                    <Stack spacing={1}>
                      <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                        <Typography variant="body2" color="text.secondary">Cluster HHI:</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {riskData.concentration_metrics.mst_clusters.cluster_hhi?.toFixed(4)}
                        </Typography>
                      </Box>
                      <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                        <Typography variant="body2" color="text.secondary">Effective Clusters:</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {riskData.concentration_metrics.mst_clusters.effective_clusters}
                        </Typography>
                      </Box>
                    </Stack>
                  ) : (
                    <Alert severity="info" sx={{ mt: 1 }}>
                      {riskData.concentration_metrics.mst_clusters?.reason ??
                        "Layer 2 MST clustering unavailable for active holdings"}
                    </Alert>
                  )}
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* Step 6: Diversification Analysis Card (FR-I1, OQ-5) */}
          <Card variant="outlined" sx={{ mb: 4, borderTop: "4px solid #6366f1" }}>
            <CardContent>
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  mb: 2,
                }}
              >
                <Typography
                  variant="h6"
                  sx={{ fontSize: "1.1rem", fontWeight: 700, color: "#1e1b4b" }}
                >
                  Portfolio Diversification &amp; Effective Number of Bets (FR-I1)
                </Typography>
                {divData && (
                  <Chip
                    label={`Default: ${divData.enb_default_type.toUpperCase()} ENB`}
                    color="primary"
                    size="small"
                    variant="outlined"
                  />
                )}
              </Box>

              {isLoadingDiv && (
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 2 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2" color="text.secondary">
                    Evaluating independent bets and universe correlations...
                  </Typography>
                </Box>
              )}

              {divData && (
                <Box>
                  {/* Two ENB Numbers with Plain Explanation */}
                  <Grid container spacing={3} sx={{ mb: 3 }}>
                    <Grid size={{ xs: 12, md: 6 }}>
                      <Box
                        sx={{
                          p: 2,
                          bgcolor: "#f8fafc",
                          borderRadius: 2,
                          border: "1px solid #e2e8f0",
                        }}
                      >
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Risk-Contribution Entropy ENB (Default)
                        </Typography>
                        <Typography
                          variant="h4"
                          sx={{ fontWeight: 700, my: 1, color: "#4338ca" }}
                        >
                          {divData.enb_risk_entropy.toFixed(2)} bets
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ display: "block" }}
                        >
                          exp(- &sum; p_i ln p_i) where p_i is percentage risk contribution.
                          Measures concentration of risk across assets. Equal to N when risk is
                          evenly balanced.
                        </Typography>
                      </Box>
                    </Grid>

                    <Grid size={{ xs: 12, md: 6 }}>
                      <Box
                        sx={{
                          p: 2,
                          bgcolor: "#f8fafc",
                          borderRadius: 2,
                          border: "1px solid #e2e8f0",
                        }}
                      >
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ fontWeight: 600 }}
                        >
                          Eigenvalue Decomposition ENB (Secondary)
                        </Typography>
                        <Typography
                          variant="h4"
                          sx={{ fontWeight: 700, my: 1, color: "#0f766e" }}
                        >
                          {divData.enb_eigen.toFixed(2)} bets
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ display: "block" }}
                        >
                          (&sum; &lambda;_i)&sup2; / &sum; &lambda;_i&sup2; over shrunk correlation
                          matrix. Measures uncorrelated statistical dimensions. Equal to N for
                          uncorrelated assets and 1 for perfect co-movement.
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>

                  {/* Cluster Concentration Breakdown & Findings */}
                  <Typography
                    variant="subtitle2"
                    sx={{ fontWeight: 700, mb: 1, color: "#334155" }}
                  >
                    MST Cluster Weight Distribution &amp; Concentration Findings
                  </Typography>

                  {/* Plain-Language Findings */}
                  <Stack spacing={1} sx={{ mb: 3 }}>
                    {divData.findings.concentration_findings?.map((f, idx) => (
                      <Alert
                        key={idx}
                        severity={f.severity === "high" ? "warning" : "info"}
                        sx={{ py: 0.5 }}
                      >
                        {f.message}
                      </Alert>
                    ))}
                  </Stack>

                  {/* Cluster Weights Grid */}
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {Object.entries(divData.cluster_weights).map(([cid, wt]) => (
                      <Grid key={cid} size={{ xs: 6, sm: 4, md: 3 }}>
                        <Box
                          sx={{
                            p: 1.5,
                            border: "1px solid #e2e8f0",
                            borderRadius: 1.5,
                            bgcolor: "#ffffff",
                          }}
                        >
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ fontWeight: 700 }}
                          >
                            {cid}
                          </Typography>
                          <Typography
                            variant="h6"
                            sx={{ fontWeight: 700, color: "#0f172a" }}
                          >
                            {(wt * 100).toFixed(1)}%
                          </Typography>
                        </Box>
                      </Grid>
                    ))}
                  </Grid>

                  {/* Candidate Suggestions */}
                  {divData.findings.candidate_suggestions &&
                    divData.findings.candidate_suggestions.length > 0 && (
                      <Box sx={{ mt: 3, pt: 2, borderTop: "1px solid #e2e8f0" }}>
                        <Typography
                          variant="subtitle2"
                          sx={{ fontWeight: 700, mb: 1, color: "#334155" }}
                        >
                          Diversification Opportunities (Universe Candidates with Low Correlation)
                        </Typography>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{ display: "block", mb: 1.5 }}
                        >
                          Universe stocks with lowest correlation to portfolio holdings (filtered
                          by ADV &ge; 10M INR and confidence &ge; 60). Wording strictly formulated
                          as &quot;would reduce concentration&quot; &mdash; not investment advice.
                        </Typography>
                        <Stack spacing={1}>
                          {divData.findings.candidate_suggestions.map((cand) => (
                            <Box
                              key={cand.symbol}
                              sx={{
                                p: 1.5,
                                bgcolor: "#f0fdf4",
                                border: "1px solid #bbf7d0",
                                borderRadius: 1.5,
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                              }}
                            >
                              <Box>
                                <Typography
                                  variant="body2"
                                  sx={{ fontWeight: 700, color: "#166534" }}
                                >
                                  {cand.symbol} &mdash; {cand.name} ({cand.industry})
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {cand.rationale}
                                </Typography>
                              </Box>
                              <Chip
                                label={`Avg Corr: ${cand.average_correlation.toFixed(2)}`}
                                size="small"
                                color="success"
                                variant="outlined"
                              />
                            </Box>
                          ))}
                        </Stack>
                      </Box>
                    )}
                </Box>
              )}
            </CardContent>
          </Card>

          {/* D3 Result Envelope: ExplainPanel */}
          {riskData.envelope && (
            <ExplainPanel
              envelope={riskData.envelope}
              title="Methodology, Covariance Shrinkage & Regulatory Envelope"
            />
          )}

        </Box>
      )}
    </Container>
  );
}
