"""Cache Yahoo statements/prices and dated NSE ownership for the exact input universe."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import yfinance as yf  # type: ignore[import-untyped]

from jobs import build_fundamentals as source

ROOT = source.ROOT
OLD = ROOT / "data/raw/fundamentals/2026-10-05"
DEFAULT = ROOT / "data/raw/fundamentals/history-yahoo-2026-10-06"


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(gzip.compress(data))
    temporary.replace(path)


def load(path: Path) -> Any:
    return json.loads(gzip.decompress(path.read_bytes()))


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def statements(frame: Any) -> dict[str, dict[str, float | None]]:
    return {
        period.date().isoformat(): {str(k): number(v) for k, v in frame[period].items()}
        for period in frame.columns
    }


def yahoo(symbol: str, directory: Path) -> dict[str, Any]:
    path = directory / "yahoo" / f"{source.safe(symbol)}.json.gz"
    if path.exists():
        return cast(dict[str, Any], load(path)["manifest"])
    ticker = yf.Ticker(symbol + ".NS")
    bundle: dict[str, Any] = {"symbol": symbol, "ticker": symbol + ".NS", "statements": {}}
    errors = {}
    for frequency in ["yearly", "quarterly"]:
        for section, method in [
            ("income", ticker.get_income_stmt),
            ("balance", ticker.get_balance_sheet),
            ("cash", ticker.get_cash_flow),
        ]:
            key = frequency + "_" + section
            for attempt in range(2):
                try:
                    frame = method(freq=frequency)
                    bundle["statements"][key] = statements(frame)
                    if frame.empty:
                        errors[key] = "Empty Yahoo response"
                    break
                except Exception as exc:
                    errors[key] = str(exc)
                    if attempt == 0:
                        time.sleep(2)
            time.sleep(0.1)
    try:
        prices = ticker.history(
            start="2021-01-01",
            end="2026-10-07",
            auto_adjust=False,
            actions=True,
            raise_errors=True,
            timeout=25,
        )
        bundle["prices"] = {
            timestamp.date().isoformat(): {str(k): number(v) for k, v in row.items()}
            for timestamp, row in prices.iterrows()
        }
    except Exception as exc:
        errors["prices"] = str(exc)
        bundle["prices"] = {}
    manifest = {
        "symbol": symbol,
        "ticker": symbol + ".NS",
        "errors": errors,
        "statement_periods": {k: sorted(v) for k, v in bundle["statements"].items()},
        "price_rows": len(bundle["prices"]),
        "yfinance_version": yf.__version__,
        "downloaded_at": datetime.now().isoformat(),
    }
    bundle["manifest"] = manifest
    save(path, bundle)
    return manifest


def release(entry: dict[str, Any]) -> date | None:
    for key in ["broadcastDate", "submissionDate", "systemDate"]:
        value = entry.get(key)
        if value:
            try:
                return source.filing_date(value.split(" ")[0])
            except (TypeError, ValueError):
                pass
    return None


def ownership(entry: dict[str, Any], directory: Path, old_records: set[str]) -> dict[str, Any]:
    symbol, record = entry["symbol"], str(entry["recordId"])
    result_path = directory / "ownership" / f"{source.safe(symbol)}_{record}.json.gz"
    if result_path.exists():
        return cast(dict[str, Any], load(result_path))
    period = source.filing_date(entry["date"]).isoformat()
    xml = directory / "nse_xbrl" / f"{source.safe(symbol)}_{record}.xml.gz"
    old_xml = OLD / "nse_xbrl" / f"{source.safe(symbol)}_{period}.xml.gz"
    if record in old_records and old_xml.exists() and not xml.exists():
        xml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old_xml, xml)
    released = release(entry)
    result: dict[str, Any] = {
        "symbol": symbol,
        "period": period,
        "record_id": record,
        "release_date": released.isoformat() if released else None,
    }
    try:
        if not xml.exists():
            source.fetch(entry["xbrl"], xml, attempts=2)
        facts = source.xbrl_row(xml)
        if facts.get("Retail_Holding") is None:
            # Cache fallback responses separately from the original snapshot.
            fallback, _ = source.nse_json_row(entry)
            for key, value in fallback.items():
                if facts.get(key) is None:
                    facts[key] = value
        result["facts"] = facts
    except Exception as exc:
        try:
            facts, _ = source.nse_json_row(entry)
            result["facts"] = facts
            result["fallback_reason"] = str(exc)
        except Exception as fallback_error:
            result["error"] = f"{exc}; fallback: {fallback_error}"
    save(result_path, result)
    return result


def acquire(directory: Path, workers: int = 4) -> None:
    universe = source.universe()
    symbols = {r["Symbol"] for r in universe}
    directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(yahoo, row["Symbol"], directory) for row in universe]
        manifest = []
        for future in as_completed(futures):
            manifest.append(future.result())
            if len(manifest) % 10 == 0:
                print(f"Yahoo {len(manifest)}/{len(universe)}", flush=True)
                (directory / "yahoo_manifest.json").write_text(json.dumps(manifest, indent=2))
    early_path = directory / "nse_filings_2023_2025.json.gz"
    early = json.loads(
        source.fetch(
            "https://www.nseindia.com/api/corporate-share-holdings-master?index=equities"
            "&from_date=01-01-2023&to_date=31-03-2025",
            early_path,
        )
    )
    recent = load(OLD / "nse_filings.json.gz")
    entries = {str(e["recordId"]): e for e in early + recent if e.get("symbol") in symbols}
    # Retain revisions too; panel construction selects the last actually published version.
    wanted = [
        e
        for e in entries.values()
        if (released := release(e)) is not None and released <= date(2026, 9, 30)
    ]
    (directory / "selected_nse_filings.json").write_text(json.dumps(wanted, indent=2))
    old_records = {
        str(e["recordId"]) for e in json.loads((OLD / "nse_chosen_filings.json").read_text())
    }
    source.CACHE = directory  # Only affects this standalone acquisition process.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(ownership, entry, directory, old_records) for entry in wanted]
        results = []
        for future in as_completed(futures):
            results.append(future.result())
            if len(results) % 50 == 0:
                print(f"NSE {len(results)}/{len(wanted)}", flush=True)
                (directory / "ownership_manifest.json").write_text(
                    json.dumps(
                        [{k: v for k, v in r.items() if k != "facts"} for r in results], indent=2
                    )
                )
    (directory / "ownership_manifest.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "facts"} for r in results], indent=2)
    )
    print("Historical acquisition complete", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    acquire(args.output.resolve(), args.workers)
