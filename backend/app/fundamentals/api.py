"""Read-only routes for the last fully published fundamentals generation."""

import json
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from backend.app.fundamentals.publication import DEFAULT_PUBLICATION, read_latest

router = APIRouter(prefix="/fundamentals", tags=["fundamentals"])


def snapshot() -> dict[str, Any]:
    try:
        result = read_latest()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No published fundamentals snapshot") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Published fundamentals unavailable") from exc
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result["snapshot_age_days"] = (
        today - datetime.fromisoformat(result["snapshot_date"]).date()
    ).days
    return result


@router.get("/latest")
def latest_fundamentals() -> dict[str, Any]:
    return snapshot()


@router.get("/status")
def fundamentals_status() -> dict[str, Any]:
    path = DEFAULT_PUBLICATION / "status.json"
    result = json.loads(path.read_text()) if path.exists() else {"status": "not_run"}
    if (DEFAULT_PUBLICATION / "latest.json").exists():
        result["last_successful_snapshot_date"] = read_latest()["snapshot_date"]
    result["checked_at"] = datetime.now(UTC).isoformat()
    return result


@router.get("/{symbol}")
def company_fundamentals(symbol: str) -> dict[str, Any]:
    latest = snapshot()
    row = next((r for r in latest["stocks"] if r["Symbol"] == symbol.upper()), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Symbol not in the published universe")
    return {
        "snapshot_date": latest["snapshot_date"],
        "published_at": latest["published_at"],
        "classification_method": latest["classification_method"],
        "model_task": latest.get("model_task", "classification"),
        "score_bands": latest.get("score_bands"),
        "score_decimals": latest.get("score_decimals"),
        **row,
    }
