import { expect, test } from "@playwright/test";

const portfolio = {
  id: "p1", name: "Demo Diversified", description: "Synthetic demo", owner_ref: "local-user",
  created_at: "2026-10-06T00:00:00Z", updated_at: "2026-10-06T00:00:00Z",
  holdings: [{ id: "h1", portfolio_id: "p1", security_id: "s1", symbol: "INFY", quantity: null, weight: 1, as_of: "2026-10-06", source: "demo" }],
};

test("five-minute demonstrator exposes risk evidence and disclaimers", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (url.includes("/meta")) return json({ platform: "PRISM", authority: "PRISM_SRS.md", universe: "NIFTY 200", disclaimer: "PRISM is descriptive risk and explanation, not investment advice." });
    if (url.includes("/ops/freshness")) return json([]);
    if (url.includes("/about/limitations")) return json({ method_version: "operations-disclosure-v1", price_frequency_label: "End-of-day prices", filings_news_poll_minutes: 30, limitations: [] });
    if (url.includes("/macro/regime/latest")) return json(null);
    if (url.includes("/portfolios/import-csv")) return json({ portfolio, errors: [], warnings: [] });
    if (url.includes("/risk-score/latest")) return json({ portfolio_id: "p1", as_of: "2026-10-06", stock_score_run_id: "sr1", diversification_run_id: null, total_score: 45, holding_risk_score: 40, structure_score: 65, structure_components: { cluster_concentration: 60, effective_bets: 70 }, confidence: 80, weighted_holding_confidence: 80, weakest_large_holding_confidence: 80, coverage: 1, status: "complete", missing_holdings: [], contributions: [], limitations: ["Descriptive risk only."], method_version: "portfolio-score-v1", config_version: "2.0.0", computed_at: "2026-10-06T00:00:00Z" });
    if (url.includes("/diversification")) return json({ id: "d1", portfolio_risk_run_id: "r1", enb_eigen: 1, enb_risk_entropy: 1, enb_default: 1, enb_default_type: "eigen", cluster_weights: { c1: 1 }, findings: { concentration_findings: [], candidate_suggestions: [] }, config_fingerprint: "f", computed_at: "2026-10-06T00:00:00Z" });
    if (url.includes("/risk-runs")) return json({ id: "r1", portfolio_id: "p1", as_of: "2026-10-06", config_version: "1.0.0", config_fingerprint: "f", input_fingerprint: "i", window_size: 250, annualisation_factor: 252, portfolio_volatility: 0.18, portfolio_variance: 0.03, portfolio_beta: 1, max_drawdown: 0.12, var_historical_95: 0.02, var_parametric_95: 0.02, es_historical_95: 0.03, es_parametric_95: 0.03, shrinkage_intensity: 0.2, concentration_metrics: { holding_hhi: 1, effective_n: 1 }, drawdown_series: [], contributions: [], status: "completed", data_sufficiency: "sufficient", envelope: { subject: "portfolio:p1", effective_time: "2026-10-06", method: "portfolio-risk", version: "1", input_fingerprint: "i", lookback: {}, units: {}, component_contributions: [], thresholds: {}, data_sufficiency: "sufficient", confidence: {}, limitations: ["Not investment advice"], computed_at: "2026-10-06T00:00:00Z" }, computed_at: "2026-10-06T00:00:00Z" });
    if (url.endsWith("/portfolios")) return json([portfolio]);
    if (url.includes("/shocks")) return json({ id: "sh1", portfolio_id: "p1", shocked_security_id: "s1", shocked_symbol: "INFY", shock_pct: -10, method_version: "scenario-v1", portfolio_impact_pct: -10, banner: "Scenario, not a forecast", assumptions: ["Historical co-movement"], results: [{ symbol: "INFY", security_id: "s1", weight: 1, estimated_impact_pct: -10, contribution_pct: -10, method_detail: {} }], created_at: "2026-10-06T00:00:00Z" });
    if (url.includes("/risk/history")) return json([]);
    if (url.includes("/fundamentals")) return json({ symbol: "INFY", company_name: "Infosys", industry: "IT", as_of: "2026-10-06", data_age_days: 10, periods: [], metrics: [], limitations: [], source_note: "Official filing adapter" });
    if (url.includes("/events")) return json({ symbol: "INFY", company_name: "Infosys", total_events: 1, events: [{ id: "e1", security_id: "s1", symbol: "INFY", company_name: "Infosys", event_type: "results", event_type_method: "rule", published_at: "2026-10-05T10:00:00Z", effective_trading_date: "2026-10-05", importance: 0.8, importance_components: {}, headline: "Quarterly filing published", source_url: "https://example.invalid/filing", sentiment: "neutral", p_pos: 0.1, p_neg: 0.1, p_neu: 0.8 }], disclaimer: "Markets may have already priced this in." });
    if (url.includes("/governance")) return json({ symbol: "INFY", security_id: "s1", as_of: "2026-10-06", pledge: { status: "missing", limitations: [] }, promoter_holding: { status: "missing" }, institutional_flow: { status: "missing", limitations: [] }, insider_activity: { status: "missing", limitations: [] }, holding_table: [], recent_insider_trades: [], limitations: [], method_version: "governance-v1", config_key: "governance_analysis" });
    if (url.includes("/macro")) return json({ symbol: "INFY", industry: "IT", as_of: "2026-10-06", exposures: [], limitations: [] });
    if (url.includes("/news")) return json({ symbol: "INFY", items: [], disclaimer: "Descriptive only." });
    if (url.includes("/risk/latest")) return json({ subject: "stock:INFY", symbol: "INFY", company_name: "Infosys", industry: "IT", effective_time: "2026-10-06", method: "risk", version: "1", method_version: "risk-v1", input_fingerprint: "i", config_fingerprint: "f", units: "points_0_to_100", total_score: 58.2, confidence: { score: 82, factors: {} }, data_sufficiency: "sufficient", data_coverage: 1, dimension_scores: { market: { score: 58.2, weight: 1, status: "ok" } }, component_contributions: [{ component_id: "ewma", dimension: "market", name: "EWMA volatility", contribution: 58.2, text: "Elevated volatility." }], components: [{ component_id: "ewma", name: "EWMA volatility", dimension: "market", direction: "higher_is_riskier", raw_value: 0.2, percentile_rank: 58.2, points: 58.2, status: "ok", status_label: "Ok", data_as_of: "2026-10-06", data_age_days: 0, evidence_ref: {} }], missing_components: [], change_explanation: { previous_score: null, total_score_change: null, top_component_changes: [] }, thresholds: {}, limitations: ["Not investment advice"], computed_at: "2026-10-06T00:00:00Z" });
    return json([]);
  });

  await page.goto("/portfolio");
  await page.getByRole("tab", { name: /CSV Upload/i }).click();
  await page.getByPlaceholder(/symbol,weight/i).fill("symbol,weight\nINFY,1.0");
  await page.getByRole("button", { name: /Upload & Calculate Risk/i }).click();
  await expect(page.getByText(/Annualised Volatility/i)).toBeVisible();

  await page.goto("/stocks/INFY");
  await expect(page.getByRole("heading", { name: "INFY" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "58.2" })).toBeVisible();
  await expect(page.getByText(/EWMA volatility/i).first()).toBeVisible();
  await expect(page.getByText(/Fundamental Risk Analysis/i).first()).toBeVisible();
  await expect(page.getByText(/Corporate Announcements/i).first()).toBeVisible();

  await page.goto("/shock");
  await expect(page.getByText(/Scenario estimate, not a prediction/i)).toBeVisible();
  await page.getByLabel("Portfolio").click();
  await page.getByRole("option", { name: "Demo Diversified" }).click();
  await page.getByLabel("Asset to Shock").click();
  await page.getByRole("option", { name: "INFY" }).click();
  await page.getByRole("button", { name: /Run Shock Simulation/i }).click();
  await expect(page.getByText(/Scenario, not a forecast/i)).toBeVisible();
  await expect(page.getByText(/not investment advice/i).first()).toBeVisible();
});
