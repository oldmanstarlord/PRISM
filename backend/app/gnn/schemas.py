from pydantic import BaseModel, Field, field_validator


class GnnPortfolioRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=200)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))
        if not normalized:
            raise ValueError("At least one symbol is required")
        return normalized
