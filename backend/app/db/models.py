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
    isin: Mapped[str | None] = mapped_column(String(12), unique=True, nullable=True, index=True)
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
    provider_symbol: Mapped[str | None] = mapped_column(String(80))
    verification_status: Mapped[str | None] = mapped_column(String(20))
    verification_reason: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityIndustryHistory(Base):
    """Point-in-time sector classification used by leakage-sensitive research."""

    __tablename__ = "security_industry_history"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "valid_from", name="uq_security_industry_history_period"
        ),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="ck_industry_dates"),
        Index("ix_security_industry_history_security_dates", "security_id", "valid_from"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id", ondelete="CASCADE"), nullable=False, index=True
    )
    industry: Mapped[str] = mapped_column(String(160), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120))
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
    provider_version: Mapped[str | None] = mapped_column(String(80))
    pipeline_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("pipeline_run.id"))
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


class MarketDataFetchResult(Base):
    __tablename__ = "market_data_fetch_result"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", name="uq_market_data_fetch_run_security"),
        Index("ix_market_data_fetch_status", "run_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    requested_start: Mapped[date] = mapped_column(Date, nullable=False)
    requested_end: Mapped[date] = mapped_column(Date, nullable=False)
    rows_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    full_refetch: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataQualityResult(Base):
    __tablename__ = "data_quality_result"
    __table_args__ = (
        UniqueConstraint("run_id", "security_id", name="uq_quality_run_security"),
        CheckConstraint("status IN ('pass', 'warn', 'fail')", name="ck_quality_status"),
        Index("ix_quality_result_run_status", "run_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="CASCADE"), nullable=False
    )
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    reasons: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    observations: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_sessions: Mapped[int | None] = mapped_column(Integer)
    last_trade_date: Mapped[date | None] = mapped_column(Date)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StockMetricDaily(Base):
    __tablename__ = "stock_metric_daily"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "metric_date", "methodology_version", name="uq_stock_metric_daily"
        ),
        CheckConstraint("quality_status IN ('pass', 'warn', 'fail')", name="ck_metric_quality"),
        Index("ix_stock_metric_date_quality", "metric_date", "quality_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("pipeline_run.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    volatility_1m: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    volatility_3m: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    volatility_6m: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    volatility_1y: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    downside_volatility: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    beta_nifty50: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    average_traded_value_20d: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    factor_volatility: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    factor_downside: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    factor_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    factor_beta: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    factor_instability: Mapped[Decimal | None] = mapped_column(Numeric(20, 12))
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    quality_status: Mapped[str] = mapped_column(String(10), nullable=False)
    observations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_reasons: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_data_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScoreCalibration(Base):
    __tablename__ = "score_calibration"
    __table_args__ = (
        UniqueConstraint(
            "calibration_date", "factor", "methodology_version", name="uq_score_calibration"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("pipeline_run.id"), nullable=False)
    calibration_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    factor: Mapped[str] = mapped_column(String(40), nullable=False)
    lower_percentile: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    upper_percentile: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    lower_value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    upper_value: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(80), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FundamentalsSnapshot(Base):
    __tablename__ = "fundamentals_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "security_id", "field", "as_of", "source", name="uq_fundamentals_snapshot"
        ),
        Index("ix_fundamentals_security_fetched", "security_id", "fetched_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    field: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)


class DataCoverageRun(Base):
    __tablename__ = "data_coverage_run"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_data_coverage_pipeline_run"),
        CheckConstraint("status IN ('completed', 'partial', 'failed')", name="ck_coverage_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_run.id", ondelete="CASCADE"), nullable=False
    )
    universe_count: Mapped[int] = mapped_column(Integer, nullable=False)
    verified_ticker_count: Mapped[int] = mapped_column(Integer, nullable=False)
    enough_history_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_pass_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_ready_count: Mapped[int] = mapped_column(Integer, nullable=False)
    fundamentals_ready_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_symbols: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    spot_checks: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    data_date: Mapped[date | None] = mapped_column(Date)
    last_update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)


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


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolio"
    __table_args__ = (
        CheckConstraint("input_mode IN ('quantities', 'weights')", name="ck_portfolio_input_mode"),
        Index("ix_portfolio_owner_archived", "owner_id", "archived_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Legacy shared-schema rows use owner_ref and intentionally remain unclaimed
    # until an authenticated UUID owner is assigned explicitly.
    owner_id: Mapped[UUID | None] = mapped_column(index=True)
    owner_ref: Mapped[str] = mapped_column(
        String(120), default="local-user", server_default="local-user", nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    input_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        CheckConstraint("cash_amount >= 0", name="ck_snapshot_cash_amount"),
        CheckConstraint("cash_weight >= 0 AND cash_weight <= 1", name="ck_snapshot_cash_weight"),
        Index("ix_portfolio_snapshot_owner", "owner_id"),
        Index("ix_portfolio_snapshot_latest", "portfolio_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    cash_amount: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), default=0, server_default="0", nullable=False
    )
    cash_weight: Mapped[Decimal] = mapped_column(
        Numeric(18, 12), default=0, server_default="0", nullable=False
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="csv", server_default="csv")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_snapshot_holding"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "security_id", name="uq_portfolio_snapshot_holding_security"
        ),
        CheckConstraint(
            "(quantity IS NOT NULL AND quantity > 0 AND target_weight IS NULL) OR "
            "(target_weight IS NOT NULL AND target_weight > 0 AND target_weight <= 1 "
            "AND quantity IS NULL)",
            name="ck_portfolio_snapshot_holding_value",
        ),
        Index("ix_portfolio_snapshot_holding_owner", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshot.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("security.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_owner_created", "owner_id", "created_at"),
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transaction"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('BUY', 'SELL', 'FEES', 'DIVIDEND', 'DEPOSIT', 'WITHDRAWAL')",
            name="ck_transaction_type",
        ),
        CheckConstraint("fees >= 0", name="ck_transaction_fees"),
        CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_transaction_quantity"),
        CheckConstraint("price IS NULL OR price > 0", name="ck_transaction_price"),
        Index("ix_portfolio_transaction_portfolio_date", "portfolio_id", "trade_date"),
        Index("ix_portfolio_transaction_owner", "owner_id"),
        Index(
            "ix_portfolio_transaction_idempotency",
            "portfolio_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    security_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security.id"), nullable=True, index=True
    )
    symbol: Mapped[str | None] = mapped_column(String(40))
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), default=Decimal("0"), server_default="0", nullable=False
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioRiskHistory(Base):
    __tablename__ = "portfolio_risk_history"
    __table_args__ = (
        Index("ix_portfolio_risk_history_portfolio_date", "portfolio_id", "valuation_date"),
        Index("ix_portfolio_risk_history_owner", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("portfolio_snapshot.id", ondelete="SET NULL"), nullable=True
    )
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    portfolio_risk_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    portfolio_classification: Mapped[str] = mapped_column(String(30), nullable=False)
    annualized_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    downside_volatility: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    diversification_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    effective_holdings: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    top_sector: Mapped[str] = mapped_column(String(160), nullable=False)
    top_sector_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    largest_holding: Mapped[str] = mapped_column(String(40), nullable=False)
    largest_holding_weight: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    indicators_summary: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(
        String(40), default="1.0.0", server_default="1.0.0", nullable=False
    )
    data_cutoff: Mapped[date | None] = mapped_column(Date, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JournalNote(TimestampMixin, Base):
    __tablename__ = "journal_note"
    __table_args__ = (
        Index("ix_journal_note_owner", "owner_id"),
        Index("ix_journal_note_owner_symbol", "owner_id", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )


class JournalDecision(TimestampMixin, Base):
    __tablename__ = "journal_decision"
    __table_args__ = (
        CheckConstraint(
            "decision_type IN ('BUY', 'HOLD', 'SELL', 'REVIEW')",
            name="ck_journal_decision_type",
        ),
        Index("ix_journal_decision_owner", "owner_id"),
        Index("ix_journal_decision_owner_symbol", "owner_id", "symbol"),
        Index("ix_journal_decision_owner_date", "owner_id", "decision_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    decision_type: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_date: Mapped[date] = mapped_column(Date, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    snapshot_id: Mapped[UUID | None] = mapped_column(nullable=True)


class ModelRun(Base):
    __tablename__ = "model_run"
    __table_args__ = (
        Index("ix_model_run_name_version", "model_name", "model_version"),
        Index("ix_model_run_status_cutoff", "status", "data_cutoff"),
        CheckConstraint(
            "status IN ('running', 'completed', 'ready', 'baseline_selected', "
            "'failed', 'untrained', 'insufficient_data', 'unavailable')",
            name="ck_model_run_status",
        ),
        CheckConstraint(
            "training_window_end >= training_window_start",
            name="ck_model_run_training_window",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    training_window_start: Mapped[date | None] = mapped_column(Date)
    training_window_end: Mapped[date | None] = mapped_column(Date)
    features: Mapped[list[object]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    hyperparameters: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="completed", server_default="completed", nullable=False
    )
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(Text)
    model_type: Mapped[str | None] = mapped_column(String(80))
    methodology_version: Mapped[str | None] = mapped_column(String(80))
    feature_schema_version: Mapped[str | None] = mapped_column(String(80))
    source_data_version: Mapped[str | None] = mapped_column(String(160))
    validation_window_start: Mapped[date | None] = mapped_column(Date)
    validation_window_end: Mapped[date | None] = mapped_column(Date)
    test_window_start: Mapped[date | None] = mapped_column(Date)
    test_window_end: Mapped[date | None] = mapped_column(Date)
    preprocessing: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    baseline_comparison: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    artifact_path: Mapped[str | None] = mapped_column(Text)
    artifact_checksum: Mapped[str | None] = mapped_column(String(64))
    library_versions: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    model_selected: Mapped[str | None] = mapped_column(String(80))
    selection_reason: Mapped[str | None] = mapped_column(Text)


class ModelPrediction(Base):
    __tablename__ = "model_prediction"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "target_type",
            "symbol",
            "prediction_date",
            name="uq_model_prediction_idempotent",
        ),
        Index("ix_model_prediction_run_target", "run_id", "target_type"),
        Index("ix_model_prediction_date_symbol", "prediction_date", "symbol"),
        Index("ix_model_prediction_portfolio", "portfolio_id"),
        CheckConstraint(
            "status IN ('ready', 'stale', 'baseline_selected', 'failed', "
            "'untrained', 'insufficient_data', 'unavailable')",
            name="ck_model_prediction_status",
        ),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="ck_model_prediction_bounds",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    portfolio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=True, index=True
    )
    security_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("security.id"), nullable=True, index=True
    )
    symbol: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    prediction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    predicted_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    lower_bound: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    upper_bound: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(16, 6))
    model_selected: Mapped[str] = mapped_column(
        String(40), default="ml_model", server_default="ml_model", nullable=False
    )
    explanation: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="ready", server_default="ready", nullable=False
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    data_cutoff: Mapped[date | None] = mapped_column(Date)
    methodology_version: Mapped[str | None] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(80))
    horizon_sessions: Mapped[int | None] = mapped_column(Integer)
    quality_status: Mapped[str | None] = mapped_column(String(20))


class GnnStockDrift(Base):
    __tablename__ = "gnn_stock_drift"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "analysis_date", "symbol", name="uq_gnn_stock_drift_run_date_symbol"
        ),
        CheckConstraint(
            "drift_percentile >= 0 AND drift_percentile <= 1",
            name="ck_gnn_drift_percentile",
        ),
        CheckConstraint(
            "alert_level IN ('normal', 'elevated', 'high')", name="ck_gnn_alert_level"
        ),
        Index("ix_gnn_stock_drift_date_level", "analysis_date", "alert_level"),
        Index("ix_gnn_stock_drift_symbol_date", "symbol", "analysis_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    industry: Mapped[str] = mapped_column(String(160), nullable=False)
    embedding_drift: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False)
    drift_percentile: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    alert_level: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_driver: Mapped[str | None] = mapped_column(String(80))
    driver_scope: Mapped[str | None] = mapped_column(String(30))
    driver_scores: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    explanation: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GnnMarketDrift(Base):
    __tablename__ = "gnn_market_drift"
    __table_args__ = (
        UniqueConstraint("run_id", "analysis_date", name="uq_gnn_market_drift_run_date"),
        Index("ix_gnn_market_drift_date", "analysis_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    mean_drift: Mapped[Decimal] = mapped_column(Numeric(16, 8), nullable=False)
    share_above_train_95pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    active_stocks: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NewsArticle(TimestampMixin, Base):
    __tablename__ = "news_article"
    __table_args__ = (
        Index("ix_news_article_published", "published_at"),
        Index("ix_news_article_simhash", "simhash"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(String(160), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    snippet: Mapped[str | None] = mapped_column(Text)
    simhash: Mapped[str | None] = mapped_column(String(64))
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    primary_article_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("news_article.id", ondelete="SET NULL")
    )
    processing_status: Mapped[str] = mapped_column(
        String(40), default="processed", server_default="processed"
    )


class NewsEntityMatch(Base):
    __tablename__ = "news_entity_match"
    __table_args__ = (
        Index("ix_news_entity_match_article_symbol", "article_id", "symbol"),
        Index("ix_news_entity_match_symbol", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("news_article.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12))
    match_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(
        String(40), default="auto_matched", server_default="auto_matched"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NewsSignal(Base):
    __tablename__ = "news_signal"
    __table_args__ = (
        Index("ix_news_signal_article_symbol", "article_id", "symbol"),
        Index("ix_news_signal_symbol", "symbol"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("news_article.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str | None] = mapped_column(String(40))
    is_market_wide: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sentiment_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=False)
    sentiment_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    processing_time_ms: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    event_category: Mapped[str] = mapped_column(String(40), nullable=False)
    event_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
