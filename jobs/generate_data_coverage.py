"""Render the permitted-source coverage snapshot as Markdown on stdout."""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from backend.app.data_sources.coverage import build_data_coverage
from backend.app.db.models import ScoreComponentValue, ScoreRun
from backend.app.db.session import SessionLocal

FUNDAMENTAL_COMPONENTS = (
    "fund_leverage",
    "fund_coverage",
    "fund_profit_trend",
    "fund_cashflow_quality",
)


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report() -> str:
    with SessionLocal() as session:
        report = build_data_coverage(session)
        latest_run = session.scalars(
            select(ScoreRun)
            .where(ScoreRun.status == "completed", ScoreRun.config_version == "1.0.0")
            .order_by(ScoreRun.completed_at.desc())
            .limit(1)
        ).first()
        fundamental_counts: dict[str, Counter[str]] = {}
        if latest_run is not None:
            rows = session.execute(
                select(ScoreComponentValue.component_id, ScoreComponentValue.status).where(
                    ScoreComponentValue.run_id == latest_run.id,
                    ScoreComponentValue.component_id.in_(FUNDAMENTAL_COMPONENTS),
                )
            ).all()
            for component_id, status in rows:
                normalized_status = "ok" if status == "flagged" else status
                fundamental_counts.setdefault(component_id, Counter())[normalized_status] += 1

    lines = [
        "# Data Coverage",
        "",
        f"Generated at: `{report.generated_at.isoformat()}`  ",
        f"Active universe: **{report.universe_size} securities**",
        "",
        (
            "Only rows attributable to a permitted production source are counted. "
            "Quarantined fixture rows and supplied files that cannot satisfy a strict "
            "importer are excluded."
        ),
        "",
        "## Dataset coverage",
        "",
        (
            "| Dataset | Source | Real or missing | Coverage status | Rows | First date | "
            "Last date | Universe | Staleness | Limitations |"
        ),
        "|---|---|---:|---:|---:|---|---|---:|---:|---|",
    ]
    for dataset_item in report.datasets:
        universe_cell = (
            f"{dataset_item.universe_covered}/{dataset_item.universe_total} "
            f"({dataset_item.universe_share:.1%})"
        )
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    dataset_item.dataset,
                    dataset_item.source,
                    dataset_item.data_status,
                    dataset_item.coverage_status,
                    dataset_item.rows,
                    dataset_item.first_date or "N/A",
                    dataset_item.last_date or "N/A",
                    universe_cell,
                    dataset_item.staleness,
                    dataset_item.limitations or "N/A",
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Risk-dimension coverage",
            "",
            "| Dimension | OK | Stale | Missing | Insufficient |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for dimension_item in report.dimensions:
        lines.append(
            f"| {dimension_item.dimension} | {dimension_item.ok} "
            f"({dimension_item.shares['ok']:.1%}) | {dimension_item.stale} "
            f"({dimension_item.shares['stale']:.1%}) | {dimension_item.missing} "
            f"({dimension_item.shares['missing']:.1%}) | {dimension_item.insufficient} "
            f"({dimension_item.shares['insufficient']:.1%}) |"
        )

    lines.extend(
        [
            "",
            "## Fundamentals component status",
            "",
            "| Component | OK | Stale | Missing | Insufficient |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for component in FUNDAMENTAL_COMPONENTS:
        counts = fundamental_counts.get(component, Counter())
        lines.append(
            f"| {component} | {counts['ok']} | {counts['stale']} | "
            f"{counts['missing']} | {counts['insufficient']} |"
        )

    before = report.previous_score
    after = report.latest_score
    before_run = before.run_id if before else "Not available (no prior approved-v1 run)"
    before_risk = before.median_risk if before else "N/A"
    before_confidence = before.median_confidence if before else "N/A"
    after_run = after.run_id if after else "Not available"
    after_risk = after.median_risk if after else "N/A"
    after_confidence = after.median_confidence if after else "N/A"
    lines.extend(
        [
            "",
            "## Score effect",
            "",
            "| Snapshot | Run | Median risk | Median confidence |",
            "|---|---|---:|---:|",
            f"| Before | {before_run} | {before_risk} | {before_confidence} |",
            f"| After | {after_run} | {after_risk} | {after_confidence} |",
            "",
            "## Still missing -- exact supply requirements",
            "",
        ]
    )
    missing = [item for item in report.datasets if item.data_status == "missing"]
    if missing:
        for missing_item in missing:
            lines.append(
                f"- **{missing_item.dataset}**: "
                f"{missing_item.limitations or 'A permitted real source is required.'}"
            )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Integrity statement",
            "",
            (
                "No fixture or invented data was written by this ingestion step. A dataset "
                "remains visibly missing when the supplied source cannot meet its strict "
                "schema or permission requirements."
            ),
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_report())
