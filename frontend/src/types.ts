export type Horizon = 1 | 5 | 20;
export type Interpretation = "normal" | "moderate" | "strong" | "extreme";

export interface RunSummary {
  signal_date: string;
  data_cutoff: string;
  completed_at: string;
  implementation_version: string;
  score_count: number;
  issue_count: number;
  exclusion_count: number;
}

export interface Score {
  symbol: string;
  industry: string;
  divergence_value: number;
  industry_percentile: number;
  interpretation: Interpretation;
  observations_used: number;
}

export interface RankingsResponse {
  run: RunSummary;
  horizon: Horizon;
  results: Score[];
}

export interface CompanyScore {
  horizon: Horizon;
  divergence_value: number;
  residual_value: number;
  industry_percentile: number;
  interpretation: Interpretation;
  alpha: number;
  beta: number;
  residual_volatility: number;
  observations_used: number;
  lookback_start: string;
  lookback_end: string;
}

export interface ComparisonPoint {
  trade_date: string;
  stock_index: number;
  benchmark_index: number;
}

export interface CompanyResponse {
  run: RunSummary;
  company: { symbol: string; name: string; industry: string };
  scores: CompanyScore[];
  comparison: {
    basis: string;
    indexed_to: number;
    peer_count: number;
    peer_symbols: string[];
    omitted_earlier_paired_observations: number;
    points: ComparisonPoint[];
  };
  limitations: string[];
}

export interface MstResponse {
  run: {
    id: string; window_start: string; window_end: string; data_cutoff: string;
    requested_symbol_count: number; included_symbol_count: number; edge_count: number;
    is_connected: boolean; is_acyclic: boolean; implementation_version: string;
    variant?: string;
    configuration: Record<string, unknown>; computed_at: string;
    exclusions: Array<{ symbol: string; reason: string; details: string }>;
  };
  variant?: string;
  stability_grade?: string | null;
  edge_persistence?: number | null;
  clusters_count?: number | null;
  nodes: Array<{
    id: string;
    symbol: string;
    industry: string;
    observations_used: number;
    degree?: number | null;
    weighted_centrality?: number | null;
    hub_rank?: number | null;
    cluster_id?: string | null;
  }>;
  edges: Array<{
    source: string; target: string; symbol_a: string; symbol_b: string;
    correlation: number; distance: number; paired_observations: number; edge_rank: number;
  }>;
  limitations: string[];
}

export interface MstStabilityResponse {
  variant: string;
  latest_stability?: {
    run_id: string;
    prior_run_id: string;
    edge_persistence: number;
    node_overlap: number;
    window_gap_days: number;
    grade: string;
    details: Record<string, unknown>;
  } | null;
  history_summary: {
    windows_evaluated: number;
    average_edge_persistence: number;
    worst_edge_persistence: number;
    worst_window?: [string, string] | null;
    thresholds: { high: number; medium: number };
  };
  default_variant: string;
  limitations: string[];
}

export interface MstClustersResponse {
  run_id: string;
  variant: string;
  cluster_rule_version: string;
  cluster_k_cut: number;
  clusters_count: number;
  clusters: Record<string, string[]>;
  members: Array<{
    security_id: string;
    symbol: string;
    cluster_id: string;
    cluster_size: number;
    cluster_rule_version: string;
  }>;
  limitations: string[];
}

export interface MstNodeMetricDetail {
  security_id: string;
  symbol: string;
  run_id: string;
  variant: string;
  degree: number;
  weighted_centrality: number;
  hub_rank: number;
  cluster_id?: string | null;
  cluster_size?: number | null;
  cluster_peers: string[];
  incident_edges: Array<{
    neighbor_symbol: string;
    correlation: number | null;
    distance: number;
    edge_rank: number;
    paired_observations: number;
  }>;
  limitations: string[];
}

export interface MetaResponse {
  platform: string;
  authority: string;
  disclaimer: string;
  universe: string;
  latest_pipeline_runs?: Record<string, unknown>;
  active_model_configs?: Record<string, { version: string; status: string; hash: string }>;
}

export interface QualitySummaryResponse {
  status: string;
  datasets: {
    securities: { active_count: number };
    raw_prices: { total_records: number; min_date: string | null; max_date: string | null };
    adjusted_prices: { total_records: number };
    corporate_actions: { total_records: number };
    benchmarks: { active_series_count: number; total_records: number };
    shares_outstanding: { total_filings: number };
    derived_market_stats: {
      total_records: number;
      zero_volume_flagged: number;
      thin_trading_flagged: number;
    };
  };
  quality_policy: string;
}

export interface FreshnessItem {
  dataset: string;
  latest_trade_date: string | null;
  latest_ingested_at: string | null;
  age_days?: number | null;
}

export interface FreshnessResponse {
  as_of_utc: string;
  datasets: FreshnessItem[];
}

export interface CrosscheckDiscrepancy {
  security_id: string;
  symbol: string;
  trade_date: string;
  source_a: string;
  source_b: string;
  close_a: number;
  close_b: number;
  rel_diff: number;
  status: string;
  details?: Record<string, unknown>;
}

export interface CrosscheckLatestResponse {
  run_id: string | null;
  checked_at: string | null;
  sources: { source_a: string; source_b: string };
  total_compared: number;
  mismatch_count: number;
  mismatch_rate: number;
  worst_discrepancies: CrosscheckDiscrepancy[];
}

export interface ResultEnvelope {
  subject?: string;
  effective_time?: string;
  method?: string;
  version?: string;
  method_version?: string;
  input_fingerprint?: string;
  inputs_ref?: Record<string, unknown>;
  lookback?: string | number | { start?: string; end?: string; window_size?: number };
  units?: string;
  thresholds?: Record<string, unknown> | Array<{ name: string; value: number | string }>;
  data_sufficiency?: string;
  confidence?: number | { score: number; factors?: Record<string, number>; caps?: string[] };
  limitations?: string[];
  computed_at?: string;
  reason?: string;
}

export interface BreakdownItem {
  key: string;
  dimension?: string;
  display_name: string;
  percentile?: number;
  risk_points?: number;
  weight?: number;
  status?: string;
  data_age_days?: number;
  reason?: string;
}

export interface PortfolioHolding {
  id: string;
  portfolio_id: string;
  security_id?: string | null;
  symbol: string;
  quantity?: number | null;
  weight: number;
  as_of: string;
  source: string;
  notes?: string | null;
}

export interface Portfolio {
  id: string;
  name: string;
  description?: string | null;
  owner_ref: string;
  created_at: string;
  updated_at: string;
  holdings: PortfolioHolding[];
}

export interface RiskContribution {
  symbol: string;
  security_id?: string | null;
  weight: number;
  asset_volatility: number;
  marginal_contribution: number;
  percent_contribution: number;
  beta?: number | null;
  notes?: string | null;
}

export interface DrawdownPoint {
  date: string;
  drawdown: number;
  portfolio_return: number;
}

export interface PortfolioRiskRun {
  id: string;
  portfolio_id: string;
  as_of: string;
  config_version: string;
  config_fingerprint: string;
  input_fingerprint: string;
  window_size: number;
  annualisation_factor: number;
  portfolio_volatility: number;
  portfolio_variance: number;
  portfolio_beta?: number | null;
  max_drawdown: number;
  var_historical_95?: number | null;
  var_parametric_95?: number | null;
  es_historical_95?: number | null;
  es_parametric_95?: number | null;
  shrinkage_intensity: number;
  concentration_metrics: {
    holding_hhi?: number;
    effective_n?: number;
    top_holding_weight?: number;
    industry_weights?: Record<string, number>;
    industry_hhi?: number;
    mst_clusters?: {
      status: string;
      reason?: string;
      cluster_weights?: Record<string, number>;
      cluster_hhi?: number;
      effective_clusters?: number;
    };
  };
  drawdown_series: DrawdownPoint[];
  contributions: RiskContribution[];
  status: string;
  data_sufficiency: string;
  envelope: ResultEnvelope;
  computed_at: string;
}

export interface RowValidationError {
  row: number;
  symbol?: string | null;
  field?: string | null;
  error: string;
}

export interface PortfolioImportResult {
  portfolio?: Portfolio | null;
  errors: RowValidationError[];
  warnings: string[];
}

export interface StockScoreItem {
  security_id: string;
  symbol: string;
  company_name: string;
  industry: string;
  total_score: number;
  confidence: number;
  data_coverage: number;
  dimension_scores: Record<string, { score: number | null; weight: number; status: string }>;
  top_reason?: {
    component_id: string;
    dimension: string;
    name: string;
    contribution: number;
    percentile?: number;
    raw_value?: number;
    text: string;
  } | null;
  limitations: string[];
  computed_at: string;
}

export interface StockScoresResponse {
  run_id: string | null;
  as_of_date: string | null;
  config_version: string;
  total_items: number;
  page: number;
  page_size: number;
  items: StockScoreItem[];
}

export interface StockRiskComponent {
  component_id: string;
  name: string;
  dimension: string;
  direction: string;
  raw_value: number | null;
  percentile_rank: number | null;
  points: number | null;
  status: string;
  status_label: string;
  data_as_of: string | null;
  data_age_days: number | null;
  evidence_ref: Record<string, unknown>;
}

export interface StockRiskEnvelope extends ResultEnvelope {
  symbol: string;
  company_name: string;
  industry: string;
  total_score: number;
  data_coverage: number;
  dimension_scores: Record<string, { score: number | null; weight: number; status: string }>;
  component_contributions: Array<{
    component_id: string;
    dimension: string;
    name: string;
    contribution: number;
    percentile?: number;
    raw_value?: number;
    text: string;
  }>;
  components: StockRiskComponent[];
}

export interface CandidateSuggestion {
  security_id: string;
  symbol: string;
  name: string;
  industry: string;
  average_correlation: number;
  adv_20: number | null;
  confidence: number | null;
  rationale: string;
}

export interface ConcentrationFinding {
  severity: "high" | "medium" | "info";
  cluster_id: string;
  weight: number;
  holding_count: number;
  total_holdings: number;
  message: string;
  members: string[];
}

export interface DiversificationResponse {
  id: string;
  portfolio_risk_run_id: string;
  enb_eigen: number;
  enb_risk_entropy: number;
  enb_default: number;
  enb_default_type: string;
  cluster_weights: Record<string, number>;
  findings: {
    concentration_findings?: ConcentrationFinding[];
    candidate_suggestions?: CandidateSuggestion[];
  };
  config_fingerprint: string;
  computed_at: string;
}

export interface ShockRequest {
  symbol: string;
  shock_pct: number;
  method?: "regression_beta" | "mst_path_decay";
}

export interface ShockResultItem {
  symbol: string;
  security_id: string | null;
  weight: number;
  estimated_impact_pct: number;
  contribution_pct: number;
  method_detail: {
    symbol?: string;
    sensitivity?: number;
    sensitivity_type?: string;
  };
}

export interface ShockScenarioResponse {
  id: string;
  portfolio_id: string;
  shocked_security_id: string | null;
  shocked_symbol: string;
  shock_pct: number;
  method_version: string;
  portfolio_impact_pct: number;
  banner: string;
  assumptions: string[];
  results: ShockResultItem[];
  created_at: string;
}

export interface FundamentalPeriodItem {
  id: string;
  period_end: string;
  period_type: string;
  basis: string;
  published_at: string;
  published_at_method: string;
  version: number;
  revenue: number | null;
  operating_profit: number | null;
  pat: number | null;
  interest_expense: number | null;
  total_debt: number | null;
  total_equity: number | null;
  total_assets: number | null;
  cash_from_operations: number | null;
  extra?: Record<string, unknown> | null;
}

export interface FundamentalMetricItem {
  metric_key: string;
  value: number | null;
  peer_percentile: number | null;
  peer_group: string;
  status: string;
  details?: Record<string, unknown> | null;
  data_age_days?: number | null;
}

export interface StockFundamentalsResponse {
  symbol: string;
  company_name: string;
  industry: string;
  sector?: string | null;
  as_of: string;
  data_age_days?: number | null;
  periods: FundamentalPeriodItem[];
  metrics: FundamentalMetricItem[];
  limitations: string[];
  source_note: string;
}


