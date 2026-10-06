"""Point-in-time and no-look-ahead tests for macro series and observations (FR-D4, D3)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from backend.app.macro.adapters.csv_adapter import CsvMacroAdapter


def test_as_of_visibility_by_published_at(tmp_path: Path) -> None:
    """Observations with published_at > cutoff must NEVER be visible point-in-time."""
    temp_dir = tmp_path / "macro_data"
    temp_dir.mkdir(parents=True, exist_ok=True)
    csv_file = temp_dir / "crude_oil.csv"

    d1 = date(2026, 1, 10)
    d2 = date(2026, 1, 11)
    d3 = date(2026, 1, 12)

    # d1 published on 2026-01-10T18:00
    # d2 published on 2026-01-11T18:00
    # d3 published on 2026-01-12T18:00
    content = (
        "date,value,published_at,version\n"
        f"{d1.isoformat()},80.0,2026-01-10T18:00:00+00:00,1\n"
        f"{d2.isoformat()},82.5,2026-01-11T18:00:00+00:00,1\n"
        f"{d3.isoformat()},85.0,2026-01-12T18:00:00+00:00,1\n"
    )
    csv_file.write_text(content, encoding="utf-8")

    adapter = CsvMacroAdapter(base_dir=temp_dir)

    # Cutoff at 2026-01-11T12:00 (midday): only d1 is visible, d2 and d3 are NOT visible
    cutoff_midday = datetime(2026, 1, 11, 12, 0, tzinfo=UTC)
    obs = adapter.fetch_observations("crude_oil", cutoff=cutoff_midday)
    assert len(obs) == 1
    assert obs[0].obs_date == d1
    assert obs[0].value == 80.0

    # Cutoff at 2026-01-11T20:00: d1 and d2 visible, d3 is NOT visible
    cutoff_evening = datetime(2026, 1, 11, 20, 0, tzinfo=UTC)
    obs2 = adapter.fetch_observations("crude_oil", cutoff=cutoff_evening)
    assert len(obs2) == 2
    assert [o.obs_date for o in obs2] == [d1, d2]


def test_versioning_support(tmp_path: Path) -> None:
    """Restated observation version is tracked without overwriting past versions."""
    temp_dir = tmp_path / "macro_versions"
    temp_dir.mkdir(parents=True, exist_ok=True)
    csv_file = temp_dir / "usd_inr.csv"

    d1 = date(2026, 1, 15)
    content = (
        "date,value,published_at,version\n"
        f"{d1.isoformat()},83.10,2026-01-15T14:00:00+00:00,1\n"
        f"{d1.isoformat()},83.15,2026-01-16T10:00:00+00:00,2\n"
    )
    csv_file.write_text(content, encoding="utf-8")

    adapter = CsvMacroAdapter(base_dir=temp_dir)

    # Cutoff on Jan 15: sees version 1 (83.10)
    cutoff_v1 = datetime(2026, 1, 15, 18, 0, tzinfo=UTC)
    obs_v1 = adapter.fetch_observations("usd_inr", cutoff=cutoff_v1)
    assert len(obs_v1) == 1
    assert obs_v1[0].value == 83.10
    assert obs_v1[0].version == 1

    # Cutoff on Jan 16: sees both versions without loss
    cutoff_v2 = datetime(2026, 1, 16, 18, 0, tzinfo=UTC)
    obs_v2 = adapter.fetch_observations("usd_inr", cutoff=cutoff_v2)
    assert len(obs_v2) == 2
    assert obs_v2[1].value == 83.15
    assert obs_v2[1].version == 2


def test_manual_macro_import_requires_actual_timezone_aware_publication(tmp_path: Path) -> None:
    missing = tmp_path / "missing_publication.csv"
    missing.write_text("date,value\n2026-10-01,12.3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="actual published_at"):
        CsvMacroAdapter(file_path=missing).fetch_observations("fii_dii_net_flows")

    naive = tmp_path / "naive_publication.csv"
    naive.write_text(
        "date,value,published_at\n2026-10-01,12.3,2026-10-01T18:00:00\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must include a timezone"):
        CsvMacroAdapter(file_path=naive).fetch_observations("fii_dii_net_flows")
