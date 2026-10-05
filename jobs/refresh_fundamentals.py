"""Refresh public fundamentals after NSE close and publish all stocks atomically."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from backend.app.fundamentals.publication import (
    DEFAULT_MODEL,
    DEFAULT_PUBLICATION,
    ROOT,
    atomic_json,
    publish,
    read_latest,
    run_lock,
)
from jobs import build_fundamentals as source

IST = ZoneInfo("Asia/Kolkata")


def normal_session_finished(now: datetime, calendar: dict[str, Any]) -> bool:
    local = now.astimezone(IST)
    if calendar["year"] != local.year:
        raise ValueError("NSE calendar does not cover current year")
    if local.weekday() >= 5 or local.date().isoformat() in calendar["holidays"]:
        return False
    return local.time().replace(tzinfo=None) >= time(16, 30)


def holiday_calendar(root: Path, current_year: int) -> dict[str, Any]:
    path = root / f"nse_calendar_{current_year}.json"
    calendar: dict[str, Any]
    # Daily revalidation picks up additional exchange holidays without static assumptions.
    try:
        response = httpx.get(
            "https://www.nseindia.com/api/holiday-master?type=trading",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"},
            timeout=30,
        )
        response.raise_for_status()
        entries = response.json()["CM"]
        dates = [datetime.strptime(r["tradingDate"], "%d-%b-%Y").date() for r in entries]
        if not dates or any(d.year != current_year for d in dates):
            raise ValueError("NSE returned a calendar for a different year")
        calendar = {
            "year": current_year,
            "holidays": [d.isoformat() for d in dates],
            "verified_at": datetime.now(UTC).isoformat(),
            "special_sessions": "Weekend/Muhurat sessions require an explicit manual run",
        }
        atomic_json(path, calendar)
        return calendar
    except (httpx.HTTPError, KeyError, ValueError):
        if not path.exists():
            raise RuntimeError("NSE calendar unavailable; automatic refresh skipped") from None
        calendar = json.loads(path.read_text())
        age = datetime.now(UTC) - datetime.fromisoformat(calendar["verified_at"])
        if age.days > 7:
            raise RuntimeError("NSE calendar stale; automatic refresh skipped") from None
        return calendar


def retain_verified_ownership(cache: Path, publication: Path, as_of: date) -> None:
    """Keep previously verified facts at their actual period, without pretending to refresh."""
    path = cache / "parsed_snapshot.json"
    rows = json.loads(path.read_text())
    if not (publication / "latest.json").exists():
        return
    previous = {r["Symbol"]: r for r in read_latest(publication)["stocks"]}
    for row in rows:
        old = previous.get(row["Symbol"], {})
        # MCX has no NSE SHP index entry. Do not substitute public ownership for retail.
        if (
            row["Symbol"] == "MCX"
            and not row.get("Shareholding_Period")
            and old.get("Shareholding_Period")
        ):
            age = (as_of - date.fromisoformat(old["Shareholding_Period"])).days
            if 0 <= age <= 200:
                fields = [k for k in old if k.startswith(("Promoter_", "FII_", "DII_", "Retail_"))]
                for key in fields + ["Number_of_Shareholders", "Shareholding_Period"]:
                    row[key] = old[key]
                row["Data_Notes"] = (
                    "Previously verified MCX ownership retained at its actual reporting date"
                )
    path.write_text(json.dumps(rows, indent=2))


def refresh(
    universe: Path,
    model: Path,
    publication: Path,
    now: datetime,
    scheduled: bool = False,
    cached_raw: Path | None = None,
) -> dict[str, Any]:
    with run_lock(publication):
        as_of = now.astimezone(IST).date()
        try:
            if scheduled:
                calendar = holiday_calendar(publication, as_of.year)
                if not normal_session_finished(now, calendar):
                    return {"status": "skipped", "reason": "No completed normal NSE session"}
                if (publication / "latest.json").exists() and read_latest(publication)[
                    "snapshot_date"
                ] == as_of.isoformat():
                    return {"status": "skipped", "reason": "Today's snapshot already published"}
            with universe.open(newline="") as file:
                symbols = [r["Symbol"] for r in csv.DictReader(file)]
            if len(symbols) != 200 or len(set(symbols)) != 200:
                raise ValueError("Nifty 200 input must contain exactly 200 unique stocks")
            if cached_raw is None:
                cache = ROOT / f"data/raw/fundamentals/{as_of}"
                staging = publication / "staging" / as_of.isoformat()
                preferred = set()
                if (publication / "latest.json").exists():
                    preferred = {
                        r["Symbol"]
                        for r in read_latest(publication)["stocks"]
                        if r.get("Financial_Basis") == "Standalone"
                    }
                source.configure(as_of, cache, staging, universe, preferred)
                source.acquire()
                source.acquire_filings()
                source.build()
                retain_verified_ownership(cache, publication, as_of)
                cached_raw = cache / "parsed_snapshot.json"
            snapshot = publish(cached_raw, model, publication, symbols)
            return {
                "status": "completed",
                "snapshot_date": snapshot["snapshot_date"],
                "stocks": snapshot["stock_count"],
            }
        except Exception as exc:
            atomic_json(
                publication / "status.json",
                {
                    "status": "failed",
                    "failed_at": datetime.now(UTC).isoformat(),
                    "error": str(exc),
                    "previous_success_retained": True,
                },
            )
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, default=source.UNIVERSE_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--publication", type=Path, default=DEFAULT_PUBLICATION)
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument(
        "--cached-raw", type=Path, help="Explicit offline replay; retains the source snapshot date"
    )
    args = parser.parse_args()
    if args.scheduled and args.cached_raw:
        parser.error("Scheduled refresh must acquire current sources, not replay cached data")
    print(
        json.dumps(
            refresh(
                args.universe,
                args.model,
                args.publication,
                datetime.now(UTC),
                args.scheduled,
                args.cached_raw,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
