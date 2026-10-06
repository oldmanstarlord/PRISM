"""Constructed-data tests for honest coverage classification and arithmetic."""

from backend.app.data_sources.coverage import (
    combine_component_statuses,
    summarize_status_counts,
)


def test_component_status_reduction_is_conservative() -> None:
    assert combine_component_statuses([]) == "missing"
    assert combine_component_statuses(["missing", "missing"]) == "missing"
    assert combine_component_statuses(["ok", "ok"]) == "ok"
    assert combine_component_statuses(["flagged", "ok"]) == "ok"
    assert combine_component_statuses(["ok", "missing"]) == "insufficient"
    assert combine_component_statuses(["insufficient", "missing"]) == "insufficient"
    assert combine_component_statuses(["ok", "stale"]) == "stale"


def test_constructed_coverage_counts_and_shares_include_absent_stocks() -> None:
    counts, shares = summarize_status_counts(
        ["ok"] * 5 + ["stale"] * 2 + ["insufficient"] + ["missing"],
        total=10,
    )
    assert counts == {"ok": 5, "stale": 2, "missing": 2, "insufficient": 1}
    assert shares == {"ok": 0.5, "stale": 0.2, "missing": 0.2, "insufficient": 0.1}
    assert sum(shares.values()) == 1.0
