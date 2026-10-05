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


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolio"
    __table_args__ = (
        CheckConstraint("input_mode IN ('quantities', 'weights')", name="ck_portfolio_input_mode"),
        Index("ix_portfolio_owner_archived", "owner_id", "archived_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    input_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    __tablename__ = "portfolio_holding"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "security_id", name="uq_portfolio_snapshot_security"),
        CheckConstraint(
            "(quantity IS NOT NULL AND quantity > 0 AND target_weight IS NULL) OR "
            "(target_weight IS NOT NULL AND target_weight > 0 AND target_weight <= 1 "
            "AND quantity IS NULL)",
            name="ck_portfolio_holding_value",
        ),
        Index("ix_portfolio_holding_owner", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("portfolio_snapshot.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("security.id"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(18, 12))
