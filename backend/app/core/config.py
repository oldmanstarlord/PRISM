from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", ".env"),
        env_prefix="PRISM_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str
    migration_database_url: str | None = None
    cors_origins: list[str] = ["http://localhost:5173"]
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    local_auth_enabled: bool = False
    firecrawl_api_key: SecretStr | None = None
    news_cache_path: Path = _PROJECT_ROOT / "data/processed/news.sqlite3"
    news_sources: list[str] = [
        "economictimes.indiatimes.com",
        "moneycontrol.com",
        "livemint.com",
        "business-standard.com",
        "reuters.com",
    ]
    news_query: str = "India NSE stock market company earnings financial news"
    news_rss_urls: list[str] = []
    news_max_articles: int = Field(default=8, ge=1, le=10)
    news_daily_credit_budget: int = Field(default=50, ge=0, le=10000)
    news_refresh_minutes: int = Field(default=60, ge=5, le=1440)
    news_auto_refresh: bool = True
    gnn_auto_refresh: bool = False
    gnn_history_start: date = date(2020, 1, 1)
    gnn_run_path: Path | None = None
    gnn_calibration_path: Path | None = None
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    max_request_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    request_timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    expensive_rate_limit_requests: int = Field(default=20, ge=1, le=1_000)
    expensive_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3_600)
    expensive_path_prefixes: list[str] = [
        "/api/v1/news/refresh",
        "/api/v1/ml",
        "/api/v1/news/portfolio",
        "/api/v1/news/symbol",
        "/api/v1/portfolio-analysis",
    ]

    @field_validator("database_url", "migration_database_url", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            return value

        normalized = value.strip().strip('"').strip("'")
        if normalized.startswith("postgres://"):
            normalized = "postgresql://" + normalized.removeprefix("postgres://")
        if normalized.startswith("postgresql://"):
            normalized = "postgresql+psycopg://" + normalized.removeprefix("postgresql://")

        scheme, separator, remainder = normalized.partition("://")
        if separator and "@" in remainder:
            userinfo, location = remainder.rsplit("@", 1)
            if ":" in userinfo:
                username, password = userinfo.split(":", 1)
                encoded_password = quote(unquote(password), safe="")
                normalized = f"{scheme}://{username}:{encoded_password}@{location}"

        url = make_url(normalized)
        if url.get_backend_name() != "postgresql":
            raise ValueError("PRISM requires a PostgreSQL connection URL")
        if "sslmode" not in url.query:
            url = url.update_query_dict({"sslmode": "require"})
        return url.render_as_string(hide_password=False)

    @property
    def alembic_database_url(self) -> str:
        return self.migration_database_url or self.database_url

    @model_validator(mode="after")
    def validate_deployment_security(self) -> "Settings":
        if not self.cors_origins or any(origin == "*" for origin in self.cors_origins):
            raise ValueError(
                "PRISM_CORS_ORIGINS must contain explicit origins; wildcard is forbidden"
            )
        if not self.trusted_hosts or any(host == "*" for host in self.trusted_hosts):
            raise ValueError(
                "PRISM_TRUSTED_HOSTS must contain explicit hosts; wildcard is forbidden"
            )
        if self.environment.lower() == "production":
            if self.local_auth_enabled:
                raise ValueError("Local authentication bypass cannot be enabled in production")
            if not self.supabase_url or not self.supabase_publishable_key:
                raise ValueError("Production requires Supabase authentication configuration")
            if any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins):
                raise ValueError("Production CORS origins cannot target localhost")
        if self.gnn_auto_refresh and (
            self.gnn_run_path is None or self.gnn_calibration_path is None
        ):
            raise ValueError(
                "GNN auto refresh requires PRISM_GNN_RUN_PATH and PRISM_GNN_CALIBRATION_PATH"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
