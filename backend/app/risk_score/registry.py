"""Component protocol and registry for dynamic risk score synthesis (D2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import ScoreComponentDefinition
from backend.app.risk_score.components.avg_traded_value import AvgTradedValueComponent
from backend.app.risk_score.components.beta_to_benchmark import BetaToBenchmarkComponent
from backend.app.risk_score.components.events import EventRiskPressureComponent
from backend.app.risk_score.components.ewma_volatility import EwmaVolatilityComponent
from backend.app.risk_score.components.fundamentals import (
    FundCashflowQualityComponent,
    FundCoverageComponent,
    FundLeverageComponent,
    FundProfitTrendComponent,
)
from backend.app.risk_score.components.governance import (
    GovInsiderActivityComponent,
    GovInstitutionalFlowComponent,
    GovPromoterHoldingChangeComponent,
    GovPromoterPledgeComponent,
)
from backend.app.risk_score.components.macro import MacroExposureComponent
from backend.app.risk_score.components.max_drawdown_1y import MaxDrawdown1yComponent
from backend.app.risk_score.components.mst_centrality import MstCentralityComponent
from backend.app.risk_score.components.news_policy import NewsPolicyPressureComponent
from backend.app.risk_score.components.sector_divergence import SectorDivergenceComponent
from backend.app.risk_score.components.tail_loss import TailLossComponent
from backend.app.risk_score.components.zero_volume_days import ZeroVolumeDaysComponent


class ComponentOutput(BaseModel):
    """Output envelope produced by a risk score component."""

    component_id: str
    dimension: str
    raw_value: float | None = None
    percentile_rank: float | None = None
    points: float | None = None
    status: str = "ok"  # ok | stale | missing | insufficient
    data_as_of: str | None = None
    data_age_days: int | None = None
    evidence_ref: dict[str, Any] = {}
    limitations: list[str] = []


@runtime_checkable
class Component(Protocol):
    """Legacy/Single-entity protocol for risk components."""

    component_id: str
    dimension: str
    direction: str  # higher_is_riskier | lower_is_riskier
    scope: str  # universe | industry
    min_group_size: int
    weight: float

    def compute(self, context: Any) -> ComponentOutput:
        """Compute the component score and evidence."""
        ...


@dataclass
class RegisteredComponentDefinition:
    """Metadata representing a registered component."""

    id: UUID | None
    component_id: str
    dimension: str
    name: str
    description: str
    direction: str
    scope: str
    min_group_size: int
    weight: float
    active: bool
    introduced_in_step: str
    handler: Any | None = None


# Default seed definitions representing baseline Step 1 schema
DEFAULT_SEED_DEFINITIONS: list[RegisteredComponentDefinition] = [
    RegisteredComponentDefinition(
        id=None,
        component_id="volatility_60d",
        dimension="market",
        name="60-Day Realised Volatility",
        description="Annualised standard deviation of trailing 60 trading day log returns.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="max_drawdown_250d",
        dimension="market",
        name="250-Day Maximum Drawdown",
        description="Peak-to-trough decline over the trailing 250 trading day window.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="downside_deviation_60d",
        dimension="market",
        name="60-Day Downside Semi-Deviation",
        description="Standard deviation of negative daily returns below zero over 60 trading days.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="amihud_illiquidity_60d",
        dimension="liquidity",
        name="60-Day Amihud Illiquidity Ratio",
        description="Average ratio of absolute daily return to daily rupee volume.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="turnover_ratio_60d",
        dimension="liquidity",
        name="60-Day Turnover Ratio",
        description="Average daily trading volume relative to shares outstanding.",
        direction="lower_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="mst_degree_centrality",
        dimension="structure",
        name="MST Degree Centrality",
        description="Number of incident edges in the approved Layer 2 Minimum Spanning Tree.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="sector_divergence_residual_20d",
        dimension="relative",
        name="20-Day Sector Divergence Residual",
        description="Standardized residual from Layer 1 sector-divergence-v1 trailing OLS.",
        direction="higher_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 5",
    ),
    # Fundamental/governance/event/macro placeholders
    RegisteredComponentDefinition(
        id=None,
        component_id="debt_to_equity",
        dimension="fundamentals",
        name="Debt to Equity Ratio",
        description="Total debt divided by total shareholder equity from latest filing.",
        direction="higher_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 2",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="interest_coverage",
        dimension="fundamentals",
        name="Interest Coverage Ratio",
        description="EBIT divided by interest expenses from trailing 12-month statements.",
        direction="lower_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 2",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="promoter_pledging_pct",
        dimension="governance",
        name="Promoter Pledged Shares Percentage",
        description="Percentage of promoter shareholding that is pledged.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 2",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="filing_sentiment_negative",
        dimension="events",
        name="Negative Filing Sentiment Probability",
        description="FinBERT negative sentiment probability on latest exchange filings.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 2",
    ),
    RegisteredComponentDefinition(
        id=None,
        component_id="macro_rate_sensitivity",
        dimension="macro",
        name="Interest Rate Beta",
        description="Sensitivity of stock returns to Indian 10-year benchmark yield changes.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=False,
        introduced_in_step="Step 3",
    ),
]

# Active Step 5 price-side component definitions
STEP_5_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "ewma_volatility": RegisteredComponentDefinition(
        id=None,
        component_id="ewma_volatility",
        dimension="market",
        name="EWMA Realised Volatility",
        description="Annualised EWMA return volatility with decay factor (lambda=0.94).",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "beta_to_benchmark": RegisteredComponentDefinition(
        id=None,
        component_id="beta_to_benchmark",
        dimension="market",
        name="Benchmark Beta",
        description="Rolling 250-day OLS market beta relative to NIFTY 200 benchmark index.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "max_drawdown_1y": RegisteredComponentDefinition(
        id=None,
        component_id="max_drawdown_1y",
        dimension="market",
        name="1-Year Maximum Drawdown",
        description="Peak-to-trough decline over trailing 250 trading days.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "tail_loss": RegisteredComponentDefinition(
        id=None,
        component_id="tail_loss",
        dimension="market",
        name="Historical Tail Loss (Expected Shortfall)",
        description="Historical Expected Shortfall at 95% confidence over trailing 250 days.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "avg_traded_value": RegisteredComponentDefinition(
        id=None,
        component_id="avg_traded_value",
        dimension="liquidity",
        name="20-Day Average Daily Traded Value",
        description="Rolling 20-day mean of daily rupee traded value (lower is riskier).",
        direction="lower_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "zero_volume_days": RegisteredComponentDefinition(
        id=None,
        component_id="zero_volume_days",
        dimension="liquidity",
        name="Zero Volume Days",
        description="Count of non-trading or zero-volume days over trailing 60 trading days.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "mst_centrality": RegisteredComponentDefinition(
        id=None,
        component_id="mst_centrality",
        dimension="structure",
        name="MST Graph Centrality",
        description="Weighted incident edge correlation centrality in approved correlation MST.",
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
    "sector_divergence": RegisteredComponentDefinition(
        id=None,
        component_id="sector_divergence",
        dimension="relative",
        name="20-Day Sector Divergence",
        description="Absolute 20-day residual divergence score from Layer 1.",
        direction="higher_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 5",
    ),
}

# Active Step 7 fundamental component definitions
STEP_7_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "fund_leverage": RegisteredComponentDefinition(
        id=None,
        component_id="fund_leverage",
        dimension="fundamentals",
        name="Financial Leverage",
        description=(
            "Total Debt to Total Equity (or Assets to Equity for banks) relative "
            "to industry peers (higher is riskier)."
        ),
        direction="higher_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 7",
    ),
    "fund_coverage": RegisteredComponentDefinition(
        id=None,
        component_id="fund_coverage",
        dimension="fundamentals",
        name="Solvency & Interest Coverage",
        description=("Operating profit to interest expense coverage ratio (lower is riskier)."),
        direction="lower_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 7",
    ),
    "fund_profit_trend": RegisteredComponentDefinition(
        id=None,
        component_id="fund_profit_trend",
        dimension="fundamentals",
        name="TTM Profit Growth Trend",
        description=(
            "Trailing 12-month net profit YoY growth rate relative to industry peers "
            "(lower is riskier)."
        ),
        direction="lower_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 7",
    ),
    "fund_cashflow_quality": RegisteredComponentDefinition(
        id=None,
        component_id="fund_cashflow_quality",
        dimension="fundamentals",
        name="Cash Flow Quality (CFO / PAT)",
        description=(
            "Operating cash flow to net profit ratio over trailing 12 months (lower is riskier)."
        ),
        direction="lower_is_riskier",
        scope="industry",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 7",
    ),
}

# Active Step 8 governance component definitions
STEP_8_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "gov_promoter_pledge": RegisteredComponentDefinition(
        id=None,
        component_id="gov_promoter_pledge",
        dimension="governance",
        name="Promoter Pledge Risk",
        description=(
            "Promoter shares pledged as % of promoter holding (level + 2-quarter trend). "
            "Higher pledge levels and rising pledge trends are riskier."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 8",
    ),
    "gov_promoter_holding_change": RegisteredComponentDefinition(
        id=None,
        component_id="gov_promoter_holding_change",
        dimension="governance",
        name="Promoter Holding Change",
        description=(
            "Change in promoter group shareholding % over last 2 reported quarters. "
            "A declining promoter stake signals reduced confidence (higher is riskier)."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 8",
    ),
    "gov_institutional_flow": RegisteredComponentDefinition(
        id=None,
        component_id="gov_institutional_flow",
        dimension="governance",
        name="Institutional Flow (FII + DII)",
        description=(
            "Combined FII + DII holding % change over last 2 reported quarters. "
            "Net institutional outflow (negative change) is riskier."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 8",
    ),
    "gov_insider_activity": RegisteredComponentDefinition(
        id=None,
        component_id="gov_insider_activity",
        dimension="governance",
        name="Net Insider Selling Activity",
        description=(
            "Net insider selling value relative to market cap over rolling window. "
            "Higher net sell ratio is riskier."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 8",
    ),
}

# Active Step 9 macro component definitions
STEP_9_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "macro_exposure": RegisteredComponentDefinition(
        id=None,
        component_id="macro_exposure",
        dimension="macro",
        name="Macroeconomic Regime & Sector Sensitivity",
        description=(
            "Evaluates stock vulnerability to macro shocks (Crude, FX, Rates, Volatility, Flows) "
            "transmitted through sector sensitivities, scaled by market regime state."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 9",
    ),
}

# Active Step 10 event risk component definitions
STEP_10_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "event_risk_pressure": RegisteredComponentDefinition(
        id=None,
        component_id="event_risk_pressure",
        dimension="events",
        name="Event Risk Pressure",
        description=(
            "Recency-decayed pressure from exchange corporate announcements, "
            "weighted by event type, parsed severity, and sentiment direction."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=1.0,
        active=True,
        introduced_in_step="Step 10",
    ),
}

# Active Step 11 news & policy component definitions
STEP_11_COMPONENT_DEFINITIONS: dict[str, RegisteredComponentDefinition] = {
    "news_policy_pressure": RegisteredComponentDefinition(
        id=None,
        component_id="news_policy_pressure",
        dimension="macro",
        name="News & Policy Headwind Pressure",
        description=(
            "Recency-decayed severity of matched regulatory and policy headwinds for the "
            "stock's industry, mapped with deterministic economic rationales."
        ),
        direction="higher_is_riskier",
        scope="universe",
        min_group_size=5,
        weight=0.05,
        active=True,
        introduced_in_step="Step 11",
    ),
}

BUILTIN_COMPONENT_CLASSES: dict[str, type] = {
    "ewma_volatility": EwmaVolatilityComponent,
    "beta_to_benchmark": BetaToBenchmarkComponent,
    "max_drawdown_1y": MaxDrawdown1yComponent,
    "tail_loss": TailLossComponent,
    "avg_traded_value": AvgTradedValueComponent,
    "zero_volume_days": ZeroVolumeDaysComponent,
    "mst_centrality": MstCentralityComponent,
    "sector_divergence": SectorDivergenceComponent,
    "fund_leverage": FundLeverageComponent,
    "fund_coverage": FundCoverageComponent,
    "fund_profit_trend": FundProfitTrendComponent,
    "fund_cashflow_quality": FundCashflowQualityComponent,
    # Step 8: Governance components
    "gov_promoter_pledge": GovPromoterPledgeComponent,
    "gov_promoter_holding_change": GovPromoterHoldingChangeComponent,
    "gov_institutional_flow": GovInstitutionalFlowComponent,
    "gov_insider_activity": GovInsiderActivityComponent,
    # Step 9: Macro components
    "macro_exposure": MacroExposureComponent,
    # Step 10: Event components
    "event_risk_pressure": EventRiskPressureComponent,
    # Step 11: News & Policy components
    "news_policy_pressure": NewsPolicyPressureComponent,
}


@dataclass
class ComponentRegistry:
    """Registry managing active and registered risk components (D2)."""

    _definitions: dict[str, RegisteredComponentDefinition] = field(default_factory=dict)
    _handlers: dict[str, Any] = field(default_factory=dict)
    _classes: dict[str, type] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for seed in DEFAULT_SEED_DEFINITIONS:
            self._definitions[seed.component_id] = seed
        for key, cls in BUILTIN_COMPONENT_CLASSES.items():
            self._classes[key] = cls

    def load_from_db(self, session: Session) -> None:
        """Load or refresh component definitions from score_component_definition table."""
        rows = session.scalars(select(ScoreComponentDefinition)).all()
        for row in rows:
            self._definitions[row.component_id] = RegisteredComponentDefinition(
                id=row.id,
                component_id=row.component_id,
                dimension=row.dimension,
                name=row.name,
                description=row.description,
                direction=row.direction,
                scope=row.scope,
                min_group_size=row.min_group_size,
                weight=float(row.weight),
                active=row.active,
                introduced_in_step=row.introduced_in_step,
                handler=self._handlers.get(row.component_id),
            )

    def register_handler(self, handler: Any) -> None:
        """Register a Python implementation for a component."""
        cid = getattr(handler, "component_id", getattr(handler, "key", None))
        if cid is not None:
            self._handlers[cid] = handler
            if cid in self._definitions:
                self._definitions[cid].handler = handler

    def register_class(self, key: str, cls: type) -> None:
        """Register a component class by key (D2)."""
        self._classes[key] = cls

    def get_class(self, key: str) -> type | None:
        return self._classes.get(key)

    def get_instance(self, key: str) -> Any | None:
        if key in self._handlers:
            return self._handlers[key]
        cls = self._classes.get(key)
        if cls is not None:
            instance = cls()
            self._handlers[key] = instance
            return instance
        return None

    def get_definition(self, component_id: str) -> RegisteredComponentDefinition | None:
        return (
            self._definitions.get(component_id)
            or STEP_5_COMPONENT_DEFINITIONS.get(component_id)
            or STEP_7_COMPONENT_DEFINITIONS.get(component_id)
            or STEP_8_COMPONENT_DEFINITIONS.get(component_id)
            or STEP_9_COMPONENT_DEFINITIONS.get(component_id)
            or STEP_10_COMPONENT_DEFINITIONS.get(component_id)
            or STEP_11_COMPONENT_DEFINITIONS.get(component_id)
        )

    def get_handler(self, component_id: str) -> Any | None:
        return self._handlers.get(component_id)

    def list_components(
        self,
        dimension: str | None = None,
        active_only: bool = False,
    ) -> list[RegisteredComponentDefinition]:
        """List registered components with optional dimension and active filters."""
        result = list(self._definitions.values())
        if dimension is not None:
            result = [c for c in result if c.dimension == dimension]
        if active_only:
            result = [c for c in result if c.active]
        return result


# Global default registry instance
registry = ComponentRegistry()
