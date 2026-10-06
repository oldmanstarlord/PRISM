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
  distance_scale?: Array<{ correlation: number; distance: number; label: string }>;
  edge_thickness_legend?: Array<{ correlation: number; width: number }>;
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
  confidence?: number | {
    score: number;
    factors?: Record<string, ConfidenceFactor>;
    caps?: string[];
  };
  limitations?: string[];
  computed_at?: string;
  reason?: string;
}

export interface ConfidenceFactor {
  value: number;
  weight: number;
  description: string;
  cap_applied?: string | null;
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
  weight: number;
  evidence_ref: Record<string, unknown>;
}

export interface MissingRiskComponent {
  component_id: string;
  name: string;
  dimension: string;
  status: string;
  reason: string;
}

export interface ComponentChange {
  component_id: string;
  name: string;
  dimension: string | null;
  point_change: number;
  percentile_change: number;
  text: string;
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
  missing_components: MissingRiskComponent[];
  change_explanation: {
    previous_score: number | null;
    total_score_change: number | null;
    top_component_changes: ComponentChange[];
  };
}

export interface PortfolioRiskScore {
  portfolio_id: string;
  as_of: string;
  stock_score_run_id: string;
  diversification_run_id: string | null;
  total_score: number;
  holding_risk_score: number;
  structure_score: number | null;
  structure_components: {
    cluster_concentration?: number | null;
    effective_bets?: number | null;
  };
  confidence: number;
  weighted_holding_confidence: number;
  weakest_large_holding_confidence: number | null;
  coverage: number;
  status: string;
  missing_holdings: string[];
  contributions: Array<{
    symbol: string;
    weight: number;
    risk_score: number;
    confidence: number;
    weighted_risk_points: number;
  }>;
  limitations: string[];
  method_version: string;
  config_version: string;
  computed_at: string;
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

export interface GovernancePledgeInfo {
  quarter_end: string | null;
  pledge_level_pct: number | null;
  pledge_change_pct: number | null;
  n_quarters_available: number;
  status: string;
  limitations: string[];
}

export interface GovernancePromoterInfo {
  promoter_pct: number | null;
  promoter_change_pct: number | null;
  status: string;
}

export interface GovernanceInstitutionalInfo {
  quarter_end: string | null;
  fii_pct: number | null;
  dii_pct: number | null;
  combined_pct: number | null;
  institutional_change_pct: number | null;
  n_quarters_available: number;
  status: string;
  limitations: string[];
}

export interface GovernanceInsiderInfo {
  window_days: number;
  window_start: string;
  window_end: string;
  buy_value_inr: number;
  sell_value_inr: number;
  net_sell_value_inr: number;
  trade_count: number;
  insider_sell_ratio: number | null;
  status: string;
  limitations: string[];
}

export interface ShareholdingTableRow {
  quarter_end: string;
  promoter_pct: number | null;
  promoter_pledged_pct_of_promoter: number | null;
  fii_pct: number | null;
  dii_pct: number | null;
  public_pct: number | null;
  published_at: string;
  source: string;
}

export interface InsiderTradeItem {
  person_category: string;
  txn_type: string;
  quantity: number | null;
  value_inr: number | null;
  txn_date: string;
  published_at: string;
  source: string;
}

export interface StockGovernanceResponse {
  symbol: string;
  security_id: string;
  as_of: string;
  pledge: GovernancePledgeInfo;
  promoter_holding: GovernancePromoterInfo;
  institutional_flow: GovernanceInstitutionalInfo;
  insider_activity: GovernanceInsiderInfo;
  holding_table: ShareholdingTableRow[];
  recent_insider_trades: InsiderTradeItem[];
  limitations: string[];
  method_version: string;
  config_key: string;
}

// ---------------------------------------------------------------------------
// Step 9: Macro Series, Market Regime, & Sector Sensitivity Types (D1, D3, D5)
// ---------------------------------------------------------------------------

export interface MacroSeriesDefinition {
  series_key: string;
  name: string;
  source: string;
  frequency: string;
  unit: string;
  license_note: string;
  is_active: boolean;
}

export interface MacroObservation {
  obs_date: string;
  value: number;
  published_at: string;
  version: number;
}

export interface MacroSeriesDetail {
  series: MacroSeriesDefinition;
  observations: MacroObservation[];
  total_observations: number;
  latest_observation: MacroObservation | null;
}

export interface MarketRegimeResponse {
  as_of: string;
  regime: "calm" | "trending" | "stressed";
  features: {
    realised_vol_percentile?: number;
    correlation_percentile?: number;
    india_vix?: number;
    regime_multiplier?: number;
    hysteresis_applied?: boolean;
    raw_classification?: string;
    thresholds?: Record<string, number>;
  };
  config_version: string;
  computed_at?: string;
}

export interface SectorMacroSensitivity {
  industry: string;
  series_key: string;
  series_name?: string | null;
  window_end: string;
  beta: number;
  t_stat: number;
  n_obs: number;
  p_value: number;
  is_significant: boolean;
  config_version: string;
}

export interface StockMacroExposure {
  symbol: string;
  industry: string;
  regime: string;
  regime_multiplier: number;
  macro_score: number | null;
  sensitivities: SectorMacroSensitivity[];
  recent_shocks: Record<
    string,
    {
      move_21d: number;
      z_score: number;
      vol_252d: number;
      latest_val: number;
    }
  >;
  limitations: string[];
}

export interface EventItem {
  id: string;
  source_document_id?: string | null;
  security_id: string;
  symbol?: string | null;
  company_name?: string | null;
  event_type: string;
  event_type_method: string;
  published_at: string;
  effective_trading_date: string;
  importance: number;
  importance_components: Record<string, unknown>;
  headline?: string | null;
  source_url?: string | null;
  sentiment?: "positive" | "negative" | "neutral" | string | null;
  p_pos?: number | null;
  p_neg?: number | null;
  p_neu?: number | null;
  evidence_span?: string | null;
  scored_at?: string | null;
  model_name?: string | null;
  model_version?: string | null;
}

export interface StockEventsResponse {
  symbol: string;
  company_name: string;
  total_events: number;
  events: EventItem[];
  disclaimer: string;
}

export interface RecentEventsResponse {
  total: number;
  events: EventItem[];
  disclaimer: string;
}

export interface NewsItem {
  id: string;
  source: string;
  published_at: string;
  ingested_at: string;
  headline: string;
  url: string;
  content_hash: string;
}

export interface PolicyRule {
  id: string;
  rule_key: string;
  description: string;
  match_keywords: string[];
  match_category: string | null;
  affected_industries: string[];
  direction: "headwind" | "tailwind" | "ambiguous" | string;
  severity: number;
  rationale: string;
  reviewer: string;
  version: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PolicyEvent {
  id: string;
  news_item_id: string;
  rule_id: string;
  matched_at: string;
  affected_industry: string;
  severity: number;
  evidence: Record<string, unknown>;
  headline?: string | null;
  source?: string | null;
  url?: string | null;
  published_at?: string | null;
  rule_key?: string | null;
  rule_description?: string | null;
  direction?: "headwind" | "tailwind" | "ambiguous" | string | null;
  rationale?: string | null;
}

export interface StockNewsItem {
  news_item: NewsItem;
  matched_events: PolicyEvent[];
  relevance_reason: string;
}

export interface StockNewsResponse {
  symbol: string;
  company_name: string;
  industry: string | null;
  items: StockNewsItem[];
  macro_pressure_points: number | null;
  disclaimer: string;
}

export interface RecentPolicyEventsResponse {
  events: PolicyEvent[];
  total_count: number;
  disclaimer: string;
}

export interface ValidationMetric {
  metric_key: string;
  component_key: string;
  value: number | null;
  baseline_value: number | null;
  n: number;
  period: string;
}

export interface ValidationRunSummary {
  id: string;
  kind: string;
  config_fingerprint: string;
  period: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  notes: {
    failures?: string[];
    survivorship_warning?: string;
    limitations?: string[];
    labelled_observation_count?: number;
    score_run_count?: number;
    evaluation_score_run_count?: number;
    walk_forward_fold_count?: number;
    ablation_recommendations?: Record<string, "keep" | "does_not_help">;
    method_version?: string;
    multiple_testing?: string;
  };
}

export interface ValidationRunDetail extends ValidationRunSummary {
  results: ValidationMetric[];
}

export interface OperationsFreshness {
  source_key: string;
  last_success_at: string | null;
  last_data_date: string | null;
  expected_cadence: number;
  grace: number;
  status: "fresh" | "stale" | "unknown";
}

export interface DataSourceRegistryItem {
  source_key: string;
  dataset: string;
  owner: string;
  access_method: "api" | "rss" | "file_download" | "manual_import";
  terms_url: string;
  license_note: string;
  cadence: string;
  expected_grace_days: number;
  status: "live" | "manual" | "tbd" | "disabled";
  freshness_status: "fresh" | "stale" | "missing" | "unknown";
  last_verified_at: string | null;
  last_success_at: string | null;
  notes: string | null;
}

export interface OperationsPipelineRun {
  id: string;
  workflow: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_summary: string | null;
}

export interface ExplainableAlert {
  id: string;
  created_at: string;
  subject_type: string;
  subject_id: string;
  alert_type: string;
  reason: string;
  inputs_ref: Record<string, unknown>;
  score: number | null;
  status: string;
  config_version: string;
  config_fingerprint: string;
}

export interface WatchlistItem {
  id: string;
  security_id: string;
  symbol: string;
  thresholds: Record<string, number>;
}

export interface Watchlist {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  items: WatchlistItem[];
}

export interface LimitationsResponse {
  method_version: string;
  price_frequency_label: string;
  filings_news_poll_minutes: number;
  limitations: string[];
}

export interface ExplanationEvidence {
  evidence_id: string;
  kind: "statistic" | "rule" | "event" | "config";
  label: string;
  value: string | number | boolean | null;
  unit: string | null;
  window: string | null;
  source_table: string;
  source_ref: string;
  as_of: string;
  data_age_days: number | null;
}

export interface ExplanationSentence {
  text: string;
  evidence_ids: string[];
}

export interface ExplanationPayload {
  schema_version: "1.0";
  headline: string;
  summary_points: ExplanationSentence[];
  sections: Array<{
    key: string;
    title: string;
    sentences: ExplanationSentence[];
    chart_spec?: Record<string, unknown> | null;
  }>;
  evidence: ExplanationEvidence[];
  limitations: string[];
  confidence: {
    level: "high" | "medium" | "low";
    reasons: ExplanationSentence[];
  };
  data_age: { days: number | null; as_of: string; status: string };
  template_version: string;
  subject: { type: string; key: string };
  disclaimer: string;
}

export interface SectorOverviewItem {
  industry: string;
  trend: string;
  return_20d: number | null;
  breadth: number | null;
  dispersion: number | null;
  stock_count: number;
  flagged_count: number;
}

export interface SectorOverviewResponse {
  subject: string;
  effective_time: string;
  method: string;
  method_version: string;
  input_fingerprint: string;
  config_fingerprint: string;
  data_age_days: number;
  computed_at: string;
  items: SectorOverviewItem[];
  limitations: string[];
}

export interface GlossaryTermItem {
  term_key: string;
  label: string;
  plain_definition: string;
  formula_text: string | null;
  see_also: string[];
  version: string;
}

export interface NewsImpactPath {
  path_type: "direct" | "rule" | "macro" | "spillover";
  direction: "headwind" | "tailwind" | "ambiguous";
  severity: number;
  exposure_score: number;
  exposure_band: "low" | "medium" | "high";
  confidence: number;
  evidence: Array<Record<string, unknown>>;
}

export interface AffectedStock {
  symbol: string | null;
  security_id: string | null;
  industry: string;
  direction: string;
  exposure_score: number;
  exposure_band: string;
  confidence: number;
  paths: NewsImpactPath[];
}

export interface NewsInsight {
  news_id: string;
  headline: string;
  source: string;
  published_at: string;
  url: string;
  severity: number;
  affected_industries: string[];
  matched_rules: string[];
  unreviewed: boolean;
  affected_stocks: AffectedStock[];
}

export interface NewsInsightsResponse {
  items: NewsInsight[];
  source_statuses: DataSourceRegistryItem[];
  limitations: string[];
}




