"""Database models for the implemented PRISM foundation."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Security(TimestampMixin, Base):
    __tablename__ = "security"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    isin: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SecurityAlias(Base):
    __tablename__ = "security_alias"
    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "valid_from", name="uq_security_alias_period"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_alias_dates"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Universe(TimestampMixin, Base):
    __tablename__ = "universe"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class UniverseMembership(Base):
    __tablename__ = "universe_membership"
    __table_args__ = (
        UniqueConstraint(
            "universe_id", "security_id", "valid_from", name="uq_universe_membership_period"
        ),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_membership_dates"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    universe_id: Mapped[UUID] = mapped_column(
        ForeignKey("universe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TradingCalendar(Base):
    __tablename__ = "trading_calendar"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    trading_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_trading_day: Mapped[bool] = mapped_column(Boolean, nullable=False)
    session_open: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_close: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceDailyRaw(Base):
    __tablename__ = "price_daily_raw"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "trade_date", "source", "source_revision", name="uq_raw_price_revision"
        ),
        CheckConstraint("high >= low", name="ck_raw_high_low"),
        CheckConstraint("volume >= 0", name="ck_raw_volume"),
        Index("ix_raw_price_security_date", "security_id", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_flags: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class PriceDailyAdjusted(Base):
    __tablename__ = "price_daily_adjusted"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "trade_date", "method_version", name="uq_adjusted_price_version"
        ),
        Index("ix_adjusted_price_security_date", "security_id", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted_open: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    adjusted_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    adjusted_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    adjusted_close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    adjustment_factor: Mapped[Decimal | None] = mapped_column(Numeric(20, 10))
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CorporateAction(Base):
    __tablename__ = "corporate_action"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "action_type", "ex_date", "source", name="uq_corporate_action"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_counts: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    quality_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    error_summary: Mapped[str | None] = mapped_column(Text)


class SignalL1(Base):
    __tablename__ = "signal_l1"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "signal_date", "implementation_version", name="uq_signal_l1"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    divergence_value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    lookback_start: Mapped[date] = mapped_column(Date, nullable=False)
    lookback_end: Mapped[date] = mapped_column(Date, nullable=False)
    observations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    implementation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectorDivergenceRun(Base):
    __tablename__ = "sector_divergence_run"
    __table_args__ = (
        UniqueConstraint(
            "signal_date",
            "implementation_version",
            "configuration_hash",
            "input_fingerprint",
            name="uq_sector_divergence_reproducible_run",
        ),
        Index("ix_sector_divergence_run_latest", "status", "signal_date", "completed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lookback_start: Mapped[date] = mapped_column(Date, nullable=False)
    implementation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    score_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    issue_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    exclusion_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text)


class SectorDivergenceScore(Base):
    __tablename__ = "sector_divergence_score"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", "horizon", name="uq_divergence_run_score"),
        CheckConstraint("horizon IN (1, 5, 20)", name="ck_divergence_score_horizon"),
        Index("ix_divergence_score_ranking", "run_id", "horizon", "divergence_value"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sector_divergence_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    industry: Mapped[str] = mapped_column(String(160), nullable=False)
    horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_value: Mapped[Decimal] = mapped_column(Numeric(24, 16), nullable=False)
    divergence_value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    alpha: Mapped[Decimal] = mapped_column(Numeric(24, 16), nullable=False)
    beta: Mapped[Decimal] = mapped_column(Numeric(24, 16), nullable=False)
    residual_volatility: Mapped[Decimal] = mapped_column(Numeric(24, 16), nullable=False)
    industry_percentile: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    interpretation: Mapped[str] = mapped_column(String(20), nullable=False)
    lookback_start: Mapped[date] = mapped_column(Date, nullable=False)
    lookback_end: Mapped[date] = mapped_column(Date, nullable=False)
    observations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    membership_source: Mapped[str] = mapped_column(String(120), nullable=False)
    adjustment_version: Mapped[str] = mapped_column(String(80), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SectorDivergenceIssue(Base):
    __tablename__ = "sector_divergence_issue"
    __table_args__ = (Index("ix_divergence_issue_run_stage", "run_id", "stage"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("sector_divergence_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    horizon: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)


class MstRun(Base):
    __tablename__ = "mst_run"
    __table_args__ = (
        UniqueConstraint(
            "window_end",
            "implementation_version",
            "configuration_hash",
            "input_fingerprint",
            name="uq_mst_reproducible_run",
        ),
        Index("ix_mst_run_latest", "status", "window_end", "computed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    universe_id: Mapped[UUID] = mapped_column(ForeignKey("universe.id"), nullable=False)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_symbol_count: Mapped[int] = mapped_column(Integer, nullable=False)
    included_symbol_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_acyclic: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    exclusions: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    configuration: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    configuration_hash: Mapped[str | None] = mapped_column(String(64))
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="completed", server_default="legacy")
    implementation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MstNode(Base):
    __tablename__ = "mst_node"
    __table_args__ = (UniqueConstraint("mst_run_id", "security_id", name="uq_mst_run_node"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mst_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    industry: Mapped[str] = mapped_column(String(160), nullable=False)
    observations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    membership_source: Mapped[str] = mapped_column(String(120), nullable=False)


class MstEdge(Base):
    __tablename__ = "mst_edge"
    __table_args__ = (
        UniqueConstraint("mst_run_id", "security_a_id", "security_b_id", name="uq_mst_edge"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mst_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_a_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    security_b_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol_a: Mapped[str | None] = mapped_column(String(40))
    symbol_b: Mapped[str | None] = mapped_column(String(40))
    correlation: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
    distance: Mapped[Decimal] = mapped_column(Numeric(18, 12), nullable=False)
    paired_observations: Mapped[int | None] = mapped_column(Integer)
    edge_rank: Mapped[int] = mapped_column(Integer, nullable=False)


class ModelConfig(TimestampMixin, Base):
    __tablename__ = "model_config"
    __table_args__ = (
        UniqueConstraint("config_key", "version", name="uq_model_config_key_version"),
        Index("ix_model_config_key_status", "config_key", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    config_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", server_default="draft", nullable=False
    )
    configuration: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(100))


class ScoreComponentDefinition(TimestampMixin, Base):
    __tablename__ = "score_component_definition"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    component_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # higher_is_riskier | lower_is_riskier
    scope: Mapped[str] = mapped_column(
        String(20), default="universe", server_default="universe", nullable=False
    )
    min_group_size: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5", nullable=False
    )
    weight: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("1.0"), server_default="1.0", nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    introduced_in_step: Mapped[str] = mapped_column(String(40), nullable=False)


class ScoreRun(Base):
    __tablename__ = "score_run"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date",
            "config_fingerprint",
            "input_fingerprint",
            name="uq_score_run_reproducible",
        ),
        Index("ix_score_run_latest", "status", "as_of_date", "completed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model_config_id: Mapped[UUID] = mapped_column(ForeignKey("model_config.id"), nullable=False)
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending", nullable=False
    )
    total_securities: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    scored_securities: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("score_run.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_kind: Mapped[str] = mapped_column(
        String(30), default="full", server_default="full", nullable=False
    )


class StockRiskResult(Base):
    __tablename__ = "stock_risk_result"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", name="uq_stock_risk_result_run_security"),
        Index("ix_stock_risk_result_ranking", "run_id", "total_score"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("score_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    total_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    data_coverage: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    dimension_scores: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    top_reasons: Mapped[list[object]] = mapped_column(JSONB, default=list, server_default="[]")
    limitations: Mapped[list[object]] = mapped_column(JSONB, default=list, server_default="[]")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScoreComponentValue(Base):
    __tablename__ = "score_component_value"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", "component_id", name="uq_score_component_val"),
        Index("ix_score_component_val_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("score_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    component_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    raw_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    percentile_rank: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    points: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # ok | stale | missing | insufficient
    data_as_of: Mapped[date | None] = mapped_column(Date)
    data_age_days: Mapped[int | None] = mapped_column(Integer)
    evidence_ref: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class ConfidenceFactorValue(Base):
    __tablename__ = "confidence_factor_value"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", "factor_name", name="uq_confidence_factor_val"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("score_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    factor_name: Mapped[str] = mapped_column(String(40), nullable=False)
    factor_value: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    cap_applied: Mapped[str | None] = mapped_column(String(80))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    run_id: Mapped[UUID | None] = mapped_column(index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_ref: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")


class BenchmarkDefinition(TimestampMixin, Base):
    __tablename__ = "benchmark_definition"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    benchmark_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default="INR", nullable=False
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False)


class BenchmarkSeries(Base):
    __tablename__ = "benchmark_series"
    __table_args__ = (
        UniqueConstraint(
            "benchmark_id",
            "trade_date",
            "source",
            "source_revision",
            name="uq_benchmark_series_revision",
        ),
        Index("ix_benchmark_series_id_date", "benchmark_id", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey("benchmark_definition.benchmark_id"), nullable=False, index=True
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    method_version: Mapped[str] = mapped_column(
        String(80), default="official_daily_v1", nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_flags: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class SecurityShareCount(Base):
    __tablename__ = "security_share_count"
    __table_args__ = (
        UniqueConstraint("security_id", "as_of", "source", name="uq_security_share_count_period"),
        Index("ix_security_share_count_sec_date", "security_id", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shares_outstanding: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SecurityMarketStat(Base):
    __tablename__ = "security_market_stat"
    __table_args__ = (
        UniqueConstraint("security_id", "trade_date", name="uq_security_market_stat_date"),
        Index("ix_security_market_stat_date", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    traded_value: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    adv_20: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 4))
    shares_used: Mapped[int | None] = mapped_column(BigInteger)
    shares_as_of: Mapped[date | None] = mapped_column(Date)
    flags: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataCrosscheck(Base):
    __tablename__ = "data_crosscheck"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "security_id", "trade_date", name="uq_data_crosscheck_run_sec_date"
        ),
        Index("ix_data_crosscheck_run_id", "run_id"),
        Index("ix_data_crosscheck_status", "status"),
        Index("ix_data_crosscheck_sec_date", "security_id", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(nullable=False)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_a: Mapped[str] = mapped_column(String(60), nullable=False)
    source_b: Mapped[str] = mapped_column(String(60), nullable=False)
    close_a: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    close_b: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    rel_diff: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # match | mismatch | missing_b
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolio"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_ref: Mapped[str] = mapped_column(
        String(120), nullable=False, default="local-user", server_default="local-user", index=True
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holding"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "as_of", "symbol", name="uq_portfolio_holding_port_date_sym"
        ),
        Index("ix_portfolio_holding_port_date", "portfolio_id", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(
        String(80), nullable=False, default="manual_entry", server_default="manual_entry"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioRiskRun(Base):
    __tablename__ = "portfolio_risk_run"
    __table_args__ = (Index("ix_portfolio_risk_run_port_date", "portfolio_id", "as_of"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    config_version: Mapped[str] = mapped_column(String(80), nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    window_size: Mapped[int] = mapped_column(
        Integer, default=250, server_default="250", nullable=False
    )
    annualisation_factor: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("252.0"), server_default="252.0", nullable=False
    )
    portfolio_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    portfolio_variance: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    portfolio_beta: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    var_historical_95: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    var_parametric_95: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    es_historical_95: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    es_parametric_95: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    shrinkage_intensity: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    concentration_metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    drawdown_series: Mapped[list[object]] = mapped_column(JSONB, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(
        String(30), default="completed", server_default="completed", nullable=False
    )
    data_sufficiency: Mapped[str] = mapped_column(
        String(60), default="sufficient", server_default="sufficient", nullable=False
    )
    envelope: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioRiskContribution(Base):
    __tablename__ = "portfolio_risk_contribution"
    __table_args__ = (
        UniqueConstraint("run_id", "symbol", name="uq_portfolio_risk_contribution_run_sym"),
        Index("ix_portfolio_risk_contrib_run", "run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_risk_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    asset_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    marginal_contribution: Mapped[Decimal] = mapped_column(Numeric(16, 10), nullable=False)
    percent_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    notes: Mapped[str | None] = mapped_column(Text)


class AnalyticsArtifact(Base):
    __tablename__ = "analytics_artifact"
    __table_args__ = (Index("ix_analytics_artifact_run_type", "run_id", "artifact_type"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(60), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MstStability(Base):
    __tablename__ = "mst_stability"
    __table_args__ = (
        UniqueConstraint("run_id", "prior_run_id", name="uq_mst_stability_runs"),
        Index("ix_mst_stability_run_id", "run_id"),
        Index("ix_mst_stability_prior_run_id", "prior_run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False
    )
    prior_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False
    )
    edge_persistence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    node_overlap: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    window_gap_days: Mapped[int] = mapped_column(Integer, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MstCluster(Base):
    __tablename__ = "mst_cluster"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "security_id", "cluster_rule_version", name="uq_mst_cluster_node_rule"
        ),
        Index("ix_mst_cluster_run_id", "run_id"),
        Index("ix_mst_cluster_sec_id", "security_id"),
        Index("ix_mst_cluster_cluster_id", "cluster_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    cluster_id: Mapped[str] = mapped_column(String(80), nullable=False)
    cluster_rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    cluster_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MstNodeMetric(Base):
    __tablename__ = "mst_node_metric"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", name="uq_mst_node_metric_run_sec"),
        Index("ix_mst_node_metric_run_id", "run_id"),
        Index("ix_mst_node_metric_sec_id", "security_id"),
        Index("ix_mst_node_metric_symbol", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("mst_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    degree: Mapped[int] = mapped_column(Integer, nullable=False)
    weighted_centrality: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    hub_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DiversificationRun(Base):
    __tablename__ = "diversification_run"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_risk_run_id",
            "config_fingerprint",
            name="uq_diversification_run_portfolio_run_cfg",
        ),
        Index("ix_diversification_run_portfolio_run_id", "portfolio_risk_run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_risk_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_risk_run.id", ondelete="CASCADE"), nullable=False
    )
    enb_eigen: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    enb_risk_entropy: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cluster_weights: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ShockScenario(Base):
    __tablename__ = "shock_scenario"
    __table_args__ = (Index("ix_shock_scenario_portfolio_id", "portfolio_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False
    )
    shocked_security_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security.id"), nullable=True
    )
    shock_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    method_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ShockResult(Base):
    __tablename__ = "shock_result"
    __table_args__ = (
        Index("ix_shock_result_scenario_id", "scenario_id"),
        Index("ix_shock_result_security_id", "security_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(
        ForeignKey("shock_scenario.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID | None] = mapped_column(ForeignKey("security.id"), nullable=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    estimated_impact_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    contribution_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    method_detail: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )


class SourceDocument(Base):
    __tablename__ = "source_document"
    __table_args__ = (
        Index("ix_source_document_security_published", "security_id", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_doc_id: Mapped[str | None] = mapped_column(String(200))
    doc_type: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at_method: Mapped[str] = mapped_column(
        String(50), default="actual", server_default="actual", nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FundamentalPeriod(Base):
    __tablename__ = "fundamental_period"
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "period_end",
            "period_type",
            "basis",
            "version",
            name="uq_fundamental_period_version",
        ),
        Index("ix_fundamental_period_sec_end_pub", "security_id", "period_end", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # quarter | year
    basis: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # consolidated | standalone | unknown
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at_method: Mapped[str] = mapped_column(
        String(50), default="actual", server_default="actual", nullable=False
    )  # actual | estimated
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True
    )
    revenue: Mapped[float | None] = mapped_column(Float)
    operating_profit: Mapped[float | None] = mapped_column(Float)
    pat: Mapped[float | None] = mapped_column(Float)
    interest_expense: Mapped[float | None] = mapped_column(Float)
    total_debt: Mapped[float | None] = mapped_column(Float)
    total_equity: Mapped[float | None] = mapped_column(Float)
    total_assets: Mapped[float | None] = mapped_column(Float)
    cash_from_operations: Mapped[float | None] = mapped_column(Float)
    extra: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FundamentalMetric(Base):
    __tablename__ = "fundamental_metric"
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "as_of",
            "metric_key",
            "peer_group",
            name="uq_fundamental_metric_sec_asof_key",
        ),
        Index("ix_fundamental_metric_asof_peer", "as_of", "metric_key", "peer_group"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    metric_key: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    source_period_end: Mapped[date | None] = mapped_column(Date)
    data_age_days: Mapped[int | None] = mapped_column(Integer)
    peer_group: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="computed", server_default="computed", nullable=False
    )  # computed | missing | insufficient | flagged
    details: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ShareholdingPattern(Base):
    """Quarterly SEBI Reg 31 shareholding disclosures (promoter/FII/DII/public)."""

    __tablename__ = "shareholding_pattern"
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "quarter_end",
            "version",
            name="uq_shareholding_pattern_version",
        ),
        CheckConstraint(
            "(promoter_pct IS NULL OR (promoter_pct >= 0 AND promoter_pct <= 100))",
            name="ck_shareholding_promoter_pct",
        ),
        CheckConstraint(
            "(fii_pct IS NULL OR (fii_pct >= 0 AND fii_pct <= 100))",
            name="ck_shareholding_fii_pct",
        ),
        Index(
            "ix_shareholding_pattern_security_quarter",
            "security_id",
            "quarter_end",
            "published_at",
        ),
        Index(
            "ix_shareholding_pattern_content_hash",
            "content_hash",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quarter_end: Mapped[date] = mapped_column(Date, nullable=False)
    promoter_pct: Mapped[float | None] = mapped_column(Float)
    promoter_pledged_pct_of_promoter: Mapped[float | None] = mapped_column(Float)
    fii_pct: Mapped[float | None] = mapped_column(Float)
    dii_pct: Mapped[float | None] = mapped_column(Float)
    public_pct: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(120), nullable=False, default="CSV_IMPORT", server_default="CSV_IMPORT"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InsiderTrade(Base):
    """SEBI PIT Regulation 7(2) and SAST Regulation 29/31 insider trade disclosures."""

    __tablename__ = "insider_trade"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_insider_trade_content_hash"),
        Index("ix_insider_trade_security_date", "security_id", "txn_date", "published_at"),
        Index("ix_insider_trade_published", "security_id", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_category: Mapped[str] = mapped_column(String(120), nullable=False)
    txn_type: Mapped[str] = mapped_column(String(40), nullable=False)  # buy|sell|pledge|revoke
    quantity: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[float | None] = mapped_column(Float)  # INR
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_document.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(
        String(120), nullable=False, default="CSV_IMPORT", server_default="CSV_IMPORT"
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MacroSeriesDefinition(TimestampMixin, Base):
    """Catalog of registered macroeconomic and market-wide series."""

    __tablename__ = "macro_series_definition"

    series_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DAILY", server_default="DAILY"
    )
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    license_note: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )


class MacroObservation(Base):
    """Point-in-time observations of macroeconomic series."""

    __tablename__ = "macro_observation"
    __table_args__ = (
        UniqueConstraint("series_key", "obs_date", "version", name="uq_macro_observation_version"),
        Index("ix_macro_obs_query", "series_key", "obs_date", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    series_key: Mapped[str] = mapped_column(
        ForeignKey("macro_series_definition.series_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MarketRegime(Base):
    """Point-in-time rule-based market regime state."""

    __tablename__ = "market_regime"
    __table_args__ = (
        UniqueConstraint("as_of", "config_version", name="uq_market_regime_as_of_version"),
        Index("ix_market_regime_as_of", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    regime: Mapped[str] = mapped_column(String(20), nullable=False)  # calm | trending | stressed
    features: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SectorMacroSensitivity(Base):
    """Rolling point-in-time regression sensitivity of industry return to macro changes."""

    __tablename__ = "sector_macro_sensitivity"
    __table_args__ = (
        UniqueConstraint(
            "industry",
            "series_key",
            "window_end",
            "config_version",
            name="uq_sector_macro_sensitivity",
        ),
        Index("ix_sector_macro_lookup", "industry", "series_key", "window_end"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    industry: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    series_key: Mapped[str] = mapped_column(
        ForeignKey("macro_series_definition.series_key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    t_stat: Mapped[float] = mapped_column(Float, nullable=False)
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False)
    p_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_significant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Step 10: Event Intelligence & Text Scoring Models (D1, D3, D4)
# ---------------------------------------------------------------------------


class EventRule(Base):
    """Rule-based mapping from exchange announcement category to canonical event type (D1)."""

    __tablename__ = "event_rule"

    rule_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    risk_relevant: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "negative" | "positive" | "neutral"
    version: Mapped[str] = mapped_column(String(20), default="v1.0.0", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EventItem(Base):
    """Normalized point-in-time company announcement linked to security and trade date (D4)."""

    __tablename__ = "event_item"
    __table_args__ = (
        Index("ix_event_item_sec_pub", "security_id", "published_at"),
        Index("ix_event_item_effective", "security_id", "effective_trading_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_document.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False
    )
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type_method: Mapped[str] = mapped_column(
        String(20), default="rule", nullable=False
    )  # "rule" | "model"
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    importance_components: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TextScore(Base):
    """Text-level sentiment and evidence scoring record (FinBERT / rule-based) for an event item."""

    __tablename__ = "text_score"
    __table_args__ = (Index("ix_text_score_item_model", "item_id", "model_name", "model_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    item_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_item.id", ondelete="CASCADE"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    sentiment: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "positive" | "negative" | "neutral"
    p_pos: Mapped[float] = mapped_column(Float, nullable=False)
    p_neg: Mapped[float] = mapped_column(Float, nullable=False)
    p_neu: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(50))
    importance: Mapped[float | None] = mapped_column(Float)
    evidence_span: Mapped[str | None] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- Step 11: Timestamped News Items & Explainable Policy-to-Sector Rules ---


class NewsItem(Base):
    """Timestamped public news or regulatory press release item (point-in-time, D4)."""

    __tablename__ = "news_item"
    __table_args__ = (
        Index("ix_news_item_published", "published_at"),
        Index("ix_news_item_source", "source"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NewsSecurityLink(Base):
    """Entity linking connecting a news item to a specific listed security."""

    __tablename__ = "news_security_link"
    __table_args__ = (
        Index("ix_news_sec_link_sec", "security_id"),
        Index("ix_news_sec_link_item", "news_item_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    news_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("news_item.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(String(30), nullable=False)  # "symbol" | "isin" | "name"
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PolicyRule(Base):
    """Editable, versioned policy-to-sector transmission rule (D1)."""

    __tablename__ = "policy_rule"
    __table_args__ = (Index("ix_policy_rule_key_version", "rule_key", "version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    match_keywords: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    match_category: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_industries: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "headwind" | "tailwind" | "ambiguous"
    severity: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 10.0
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PolicyEvent(Base):
    """Deterministic match between a timestamped news item and a policy rule (D3, D4)."""

    __tablename__ = "policy_event"
    __table_args__ = (
        Index("ix_policy_event_industry_matched", "affected_industry", "matched_at"),
        Index("ix_policy_event_news", "news_item_id"),
        Index("ix_policy_event_rule", "rule_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    news_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("news_item.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy_rule.id", ondelete="CASCADE"), nullable=False
    )
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    affected_industry: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValidationRun(Base):
    """One reproducible, time-ordered validation experiment."""

    __tablename__ = "validation_run"
    __table_args__ = (
        UniqueConstraint(
            "kind", "config_fingerprint", "period", name="uq_validation_run_reproducible"
        ),
        Index("ix_validation_run_latest", "kind", "completed_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    period: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )


class ValidationResult(Base):
    """A scalar validation metric or explicit unavailable/failure result."""

    __tablename__ = "validation_result"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "metric_key",
            "component_key",
            "period",
            name="uq_validation_result_metric",
        ),
        Index("ix_validation_result_run_metric", "run_id", "metric_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("validation_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    component_key: Mapped[str] = mapped_column(String(100), nullable=False, server_default="score")
    value: Mapped[float | None] = mapped_column(Float)
    baseline_value: Mapped[float | None] = mapped_column(Float)
    n: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    period: Mapped[str] = mapped_column(String(80), nullable=False)


class ExperimentLog(Base):
    """Immutable record of every validation variant attempted."""

    __tablename__ = "experiment_log"
    __table_args__ = (Index("ix_experiment_log_created", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    variants_tried: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class DataFreshness(Base):
    """Latest successful observation and evaluated staleness for one source."""

    __tablename__ = "data_freshness"

    source_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_data_date: Mapped[date | None] = mapped_column(Date)
    expected_cadence: Mapped[int] = mapped_column(Integer, nullable=False)
    grace: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)


class Alert(Base):
    """Explainable, deduplicated alert with versioned input evidence."""

    __tablename__ = "alert"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_alert_dedup_key"),
        Index("ix_alert_latest", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(120), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    inputs_ref: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(30), default="open", server_default="open", nullable=False
    )
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_version: Mapped[str] = mapped_column(String(40), nullable=False)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class Watchlist(TimestampMixin, Base):
    """Named local-user watchlist."""

    __tablename__ = "watchlist"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)


class WatchlistItem(Base):
    """Security and optional per-item alert threshold overrides."""

    __tablename__ = "watchlist_item"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "security_id", name="uq_watchlist_item_security"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    watchlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("watchlist.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thresholds: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
