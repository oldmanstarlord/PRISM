import { describe, it, expect, beforeEach } from "vitest";
import {
  METRIC_REGISTRY,
  STOCK_RISK_FACTOR_WEIGHTS,
  PORTFOLIO_RISK_FACTOR_WEIGHTS,
  METHODOLOGY_VERSION,
  DEFAULT_RISK_FREE_RATE,
  ALERT_THRESHOLD_CONFIGS,
  DEFAULT_ALERT_THRESHOLDS,
  loadAlertThresholds,
  saveAlertThresholds,
  resetAlertThresholds,
} from "./methodologyRegistry";

describe("Methodology Registry Invariants & Synchronization", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("verifies methodology version and financial constants", () => {
    expect(METHODOLOGY_VERSION).toBe("2026.1");
    expect(DEFAULT_RISK_FREE_RATE).toBe(0.065);
  });

  it("verifies stock risk scoring weights sum strictly to 1.0", () => {
    const sum = Object.values(STOCK_RISK_FACTOR_WEIGHTS).reduce((a, b) => a + b, 0);
    expect(Math.abs(sum - 1.0)).toBeLessThan(1e-9);
    expect(STOCK_RISK_FACTOR_WEIGHTS.annualized_volatility).toBe(0.30);
    expect(STOCK_RISK_FACTOR_WEIGHTS.downside_volatility).toBe(0.25);
    expect(STOCK_RISK_FACTOR_WEIGHTS.max_drawdown).toBe(0.20);
    expect(STOCK_RISK_FACTOR_WEIGHTS.beta).toBe(0.15);
    expect(STOCK_RISK_FACTOR_WEIGHTS.instability).toBe(0.10);
  });

  it("verifies portfolio risk scoring weights sum strictly to 1.0", () => {
    const sum = Object.values(PORTFOLIO_RISK_FACTOR_WEIGHTS).reduce((a, b) => a + b, 0);
    expect(Math.abs(sum - 1.0)).toBeLessThan(1e-9);
    expect(PORTFOLIO_RISK_FACTOR_WEIGHTS.annualized_volatility).toBe(0.35);
    expect(PORTFOLIO_RISK_FACTOR_WEIGHTS.downside_volatility).toBe(0.25);
    expect(PORTFOLIO_RISK_FACTOR_WEIGHTS.max_drawdown).toBe(0.25);
    expect(PORTFOLIO_RISK_FACTOR_WEIGHTS.weighted_beta).toBe(0.15);
  });

  it("ensures all core risk metrics exist in the registry with definitions and units", () => {
    const requiredKeys = [
      "ANNUALIZED_VOLATILITY",
      "DOWNSIDE_VOLATILITY",
      "MAX_DRAWDOWN",
      "HISTORICAL_VAR_95",
      "HISTORICAL_ES_95",
      "PARAMETRIC_VAR_95",
      "EULER_MARGINAL_RISK",
      "EULER_COMPONENT_RISK",
      "EULER_RISK_SHARE",
      "MARKET_BETA",
      "MANTEGNA_MST_DISTANCE",
      "PORTFOLIO_RISK_SCORE_HEURISTIC",
      "STOCK_RISK_SCORE_HEURISTIC",
    ];

    for (const key of requiredKeys) {
      const metric = METRIC_REGISTRY[key];
      expect(metric, `Metric ${key} should exist`).toBeDefined();
      expect(metric.definition.length).toBeGreaterThan(10);
      expect(metric.units.length).toBeGreaterThan(0);
      expect(metric.defaultWindow.length).toBeGreaterThan(0);
      expect(metric.minObservations).toBeGreaterThanOrEqual(1);
      expect(metric.assumptions.length).toBeGreaterThan(0);
      expect(metric.limitations.length).toBeGreaterThan(0);
    }
  });

  it("verifies lowercase alias compatibility lookups", () => {
    expect(METRIC_REGISTRY["portfolio_risk_score"]).toBeDefined();
    expect(METRIC_REGISTRY["portfolio_volatility"]).toBeDefined();
    expect(METRIC_REGISTRY["downside_volatility"]).toBeDefined();
    expect(METRIC_REGISTRY["max_drawdown"]).toBeDefined();
    expect(METRIC_REGISTRY["var_historical_95"]).toBeDefined();
    expect(METRIC_REGISTRY["cvar_historical_95"]).toBeDefined();
    expect(METRIC_REGISTRY["euler_contribution"]).toBeDefined();
  });

  it("validates alert thresholds loading, custom overrides, and reset-to-default", () => {
    const portfolioId = "port-test-123";

    // 1. Initial load returns default values
    const initial = loadAlertThresholds(portfolioId);
    expect(initial.sector_ceiling).toBe(25.0);
    expect(initial.holding_concentration).toBe(20.0);
    expect(initial.risk_score).toBe(60.0);

    // 2. Saving custom thresholds clamps out-of-bound values
    const custom = {
      sector_ceiling: 40.0,
      holding_concentration: 99.0, // should be clamped to max 60.0
      risk_score: 5.0, // should be clamped to min 10.0
    };
    saveAlertThresholds(custom, portfolioId);

    const reloaded = loadAlertThresholds(portfolioId);
    expect(reloaded.sector_ceiling).toBe(40.0);
    expect(reloaded.holding_concentration).toBe(60.0);
    expect(reloaded.risk_score).toBe(10.0);

    // 3. Resetting removes custom storage and restores defaults
    const restored = resetAlertThresholds(portfolioId);
    expect(restored.sector_ceiling).toBe(25.0);
    expect(restored.holding_concentration).toBe(20.0);
    expect(restored.risk_score).toBe(60.0);
  });

  it("verifies alert threshold configs structure and bounds", () => {
    expect(ALERT_THRESHOLD_CONFIGS.length).toBeGreaterThanOrEqual(6);
    for (const cfg of ALERT_THRESHOLD_CONFIGS) {
      expect(cfg.min).toBeLessThan(cfg.max);
      expect(cfg.defaultValue).toBeGreaterThanOrEqual(cfg.min);
      expect(cfg.defaultValue).toBeLessThanOrEqual(cfg.max);
      expect(DEFAULT_ALERT_THRESHOLDS[cfg.id]).toBe(cfg.defaultValue);
    }
  });
});
