"""API contracts for the external data-source registry."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_key: str
    dataset: str
    owner: str
    access_method: str
    terms_url: str
    license_note: str
    cadence: str
    expected_grace_days: int
    status: str
    freshness_status: str
    last_verified_at: datetime | None
    last_success_at: datetime | None
    notes: str | None


class DatasetCoverageOut(BaseModel):
    source_key: str
    dataset: str
    source: str
    data_status: str
    coverage_status: str
    rows: int
    first_date: date | None
    last_date: date | None
    universe_covered: int
    universe_total: int
    universe_share: float
    staleness: str
    limitations: str | None


class DimensionCoverageOut(BaseModel):
    dimension: str
    total_stocks: int
    ok: int
    stale: int
    missing: int
    insufficient: int
    shares: dict[str, float]


class ScoreCoverageSummaryOut(BaseModel):
    run_id: str
    as_of_date: date
    config_version: str
    median_risk: float
    median_confidence: float


class DataCoverageOut(BaseModel):
    generated_at: datetime
    universe_size: int
    datasets: list[DatasetCoverageOut]
    dimensions: list[DimensionCoverageOut]
    previous_score: ScoreCoverageSummaryOut | None
    latest_score: ScoreCoverageSummaryOut | None
