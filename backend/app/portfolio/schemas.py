from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

InputMode = Literal["quantities", "weights"]


class PortfolioRowInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    value: Decimal = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be blank")
        return normalized


class PortfolioPreviewRequest(BaseModel):
    input_mode: InputMode
    rows: list[PortfolioRowInput] = Field(min_length=1, max_length=201)


class PortfolioCreateRequest(PortfolioPreviewRequest):
    name: str = Field(min_length=1, max_length=120)
    preview_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized


class PortfolioArchiveRequest(BaseModel):
    archived: bool


class PreviewHolding(BaseModel):
    security_id: UUID
    symbol: str
    company_name: str
    industry: str | None
    value: Decimal


class PortfolioPreviewResponse(BaseModel):
    valid: bool
    input_mode: InputMode
    valuation_date: date | None
    holdings: list[PreviewHolding]
    cash_value: Decimal
    errors: list[str]
    warnings: list[str]
    preview_fingerprint: str | None


class PortfolioSummary(BaseModel):
    id: UUID
    name: str
    input_mode: InputMode
    currency: str
    archived_at: datetime | None
    latest_snapshot_id: UUID
    valuation_date: date
    holding_count: int
    created_at: datetime
    updated_at: datetime


class PortfolioDetail(PortfolioSummary):
    owner_id: UUID
    cash_value: Decimal
    holdings: list[PreviewHolding]


class AuditEventResponse(BaseModel):
    id: UUID
    event_type: str
    entity_type: str
    entity_id: UUID
    details: dict[str, object]
    created_at: datetime


class TransactionCreateInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    transaction_type: Literal["BUY", "SELL", "FEES", "DIVIDEND", "DEPOSIT", "WITHDRAWAL"]
    trade_date: date
    symbol: str | None = Field(default=None, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$")
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal | None = None
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=128)

    @field_validator("symbol")
    @classmethod
    def normalize_optional_symbol(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None

    @model_validator(mode="after")
    def validate_transaction_shape(self) -> "TransactionCreateInput":
        if self.transaction_type in {"BUY", "SELL"}:
            if not self.symbol or self.quantity is None or self.price is None:
                raise ValueError("BUY and SELL require symbol, quantity, and price")
        elif self.amount is None:
            raise ValueError(f"{self.transaction_type} requires amount")
        return self


class TransactionBatchCreateRequest(BaseModel):
    transactions: list[TransactionCreateInput] = Field(min_length=1, max_length=500)


class TransactionResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    owner_id: UUID
    transaction_type: str
    symbol: str | None
    trade_date: date
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal
    fees: Decimal
    realized_pnl: Decimal | None
    notes: str | None
    idempotency_key: str | None = None
    created_at: datetime


class ReconciliationResponse(BaseModel):
    is_reconciled: bool
    derived_cash: Decimal
    derived_invested_cost: Decimal
    derived_holdings_count: int
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_net_deposits: Decimal
    total_dividends: Decimal
    total_fees: Decimal
    derived_holdings: list[dict[str, Any]]
    discrepancies: list[str]


class RiskHistoryResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    valuation_date: date
    portfolio_risk_score: float
    portfolio_classification: str
    annualized_volatility: float
    downside_volatility: float
    max_drawdown: float
    diversification_score: float
    effective_holdings: float
    top_sector: str
    top_sector_weight: float
    largest_holding: str
    largest_holding_weight: float
    indicators_summary: dict[str, Any]
    methodology_version: str = "1.0.0"
    data_cutoff: date | None = None
    computed_at: datetime


class RiskHistoryCreateInput(BaseModel):
    valuation_date: date
    portfolio_risk_score: Decimal
    portfolio_classification: str
    annualized_volatility: Decimal
    downside_volatility: Decimal
    max_drawdown: Decimal
    diversification_score: Decimal
    effective_holdings: Decimal
    top_sector: str
    top_sector_weight: Decimal
    largest_holding: str
    largest_holding_weight: Decimal
    indicators_summary: dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = "1.0.0"
    data_cutoff: date | None = None
    snapshot_id: UUID | None = None


class InitialHoldingInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=0)
    buy_price: Decimal = Field(gt=0)
    buy_date: date | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        norm = value.strip().upper()
        if not norm:
            raise ValueError("symbol cannot be blank")
        return norm


class EnsurePortfolioRequest(BaseModel):
    name: str = Field(default="Primary Portfolio", min_length=1, max_length=120)
    input_mode: InputMode = "quantities"
    initial_holdings: list[InitialHoldingInput] = Field(default_factory=list)

