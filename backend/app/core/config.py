from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import field_validator
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
