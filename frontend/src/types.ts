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

export type PortfolioInputMode = "quantities" | "weights";

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
