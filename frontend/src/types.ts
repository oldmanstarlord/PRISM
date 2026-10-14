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
    configuration: Record<string, unknown>; computed_at: string;
    exclusions: Array<{ symbol: string; reason: string; details: string }>;
  };
  nodes: Array<{ id: string; symbol: string; industry: string; observations_used: number }>;
  edges: Array<{
    source: string; target: string; symbol_a: string; symbol_b: string;
    correlation: number; distance: number; paired_observations: number; edge_rank: number;
  }>;
  limitations: string[];
}

export interface PipelineStatus {
  status: string;
  current_stage: string | null;
  failed_stage: string | null;
  latest_market_date: string | null;
  layer_1_date: string | null;
  layer_2_date: string | null;
  is_stale: boolean;
  last_successful_pipeline_at: string | null;
  latest_error: string | null;
}

export interface PortfolioPerformancePoint {
  trade_date: string;
  portfolio_index: number;
  drawdown: number;
}

export interface PortfolioHoldingAnalytics {
  symbol: string;
  industry: string;
  weight: number;
  annualized_volatility: number;
  marginal_risk: number;
  risk_contribution: number;
  divergence_20d: number | null;
  divergence_band: Interpretation | null;
}

export interface PortfolioStressInput {
  kind: "stock" | "industry";
  target: string;
  shock_percent: number;
}

export interface PortfolioAnalysisResponse {
  envelope: {
    as_of: string;
    lookback_start: string;
    data_cutoff: string;
    requested_observations: number;
    observations_used: number;
    return_frequency: string;
    annualisation_factor: number;
    weighting_assumption: string;
    missing_data_rule: string;
    implementation_version: string;
  };
  performance: {
    total_return: number;
    annualized_return: number;
    annualized_volatility: number;
    downside_volatility: number;
    max_drawdown: number;
    points: PortfolioPerformancePoint[];
  };
  holdings: PortfolioHoldingAnalytics[];
  concentration: {
    holding_hhi: number;
    effective_holdings: number;
    largest_holding_symbol: string;
    largest_holding_weight: number;
    industry_hhi: number;
    effective_industries: number;
    industry_weights: Array<{ industry: string; weight: number }>;
  };
  diversification: {
    effective_bets_risk: number;
    effective_bets_correlation: number;
    interpretation: string;
  };
  mst: {
    run_id: string;
    as_of: string;
    cluster_correlation_floor: number;
    direct_edges: Array<{
      symbol_a: string; symbol_b: string; correlation: number; distance: number;
      persistence: number | null; confidence: "unavailable" | "low" | "moderate" | "high";
    }>;
    subtree_edges: Array<{
      symbol_a: string; symbol_b: string; correlation: number; distance: number;
      persistence: number | null; confidence: "unavailable" | "low" | "moderate" | "high";
    }>;
    holding_paths: Array<{
      symbol_a: string; symbol_b: string; hops: number; average_correlation: number;
      weakest_correlation: number; positive_path_product: number; path: string[];
      minimum_edge_persistence: number | null;
      confidence: "unavailable" | "low" | "moderate" | "high";
    }>;
    bridge_stocks: Array<{ symbol: string; path_pair_count: number; is_holding: boolean }>;
    clusters: Array<{
      cluster_id: string; weight: number; holding_symbols: string[]; full_node_count: number;
    }>;
    cluster_hhi: number;
    effective_clusters: number;
    stability: {
      method: string;
      runs_compared: number;
      window_ends: string[];
      consecutive_edge_overlap: number | null;
      current_edge_persistence: number | null;
      confidence: "unavailable" | "low" | "moderate" | "high";
      reason: string;
    };
  };
  stress: null | {
    kind: "stock" | "industry";
    target: string;
    shock_percent: number;
    method: string;
    portfolio_impact_percent: number;
    results: Array<{
      symbol: string; sensitivity: number; estimated_return_percent: number;
      portfolio_contribution_percent: number;
    }>;
    assumptions: string[];
    disclaimer: string;
  };
  findings: string[];
  limitations: string[];
}

export type PortfolioInputMode = "quantities" | "weights";

export interface PortfolioAuditEvent {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioInputRow {
  symbol: string;
  value: string;
}

export interface PreviewHolding {
  security_id: string;
  symbol: string;
  company_name: string;
  industry: string | null;
  value: string;
}

export interface PortfolioPreview {
  valid: boolean;
  input_mode: PortfolioInputMode;
  valuation_date: string | null;
  holdings: PreviewHolding[];
  cash_value: string;
  errors: string[];
  warnings: string[];
  preview_fingerprint: string | null;
}

export interface PortfolioSummary {
  id: string;
  name: string;
  input_mode: PortfolioInputMode;
  currency: string;
  archived_at: string | null;
  latest_snapshot_id: string;
  valuation_date: string;
  holding_count: number;
  created_at: string;
  updated_at: string;
}

export interface PortfolioDetail extends PortfolioSummary {
  owner_id: string;
  cash_value: string;
  holdings: PreviewHolding[];
}
