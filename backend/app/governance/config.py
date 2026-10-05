"""Governance analysis configuration loaded from model_config (D1)."""

from __future__ import annotations

from pydantic import BaseModel


class GovernanceAnalysisConfig(BaseModel):
    """Typed governance analysis parameters — all values come from model_config (D1).

    No magic numbers in code; defaults here only shadow the migration seed.
    """

    # Pledge risk
    pledge_level_high_threshold: float = 20.0  # % of promoter shares pledged
    pledge_change_high_threshold: float = 5.0  # Δ% over lookback quarters

    # Promoter holding change
    promoter_change_lookback_quarters: int = 2
    promoter_decline_threshold: float = 2.0  # Δ% decline = elevated

    # Institutional flow
    institutional_flow_lookback_quarters: int = 2
    institutional_outflow_threshold: float = 3.0  # Δ% decline = elevated

    # Insider activity
    insider_window_days: int = 180
    min_market_cap_inr: float = 1_000_000_000.0
    insider_sell_ratio_elevated: float = 0.002

    # Data sufficiency
    min_quarters_for_change: int = 2
