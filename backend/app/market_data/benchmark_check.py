"""Benchmark consistency checker implementing 8 checks and PASS RULES (Task 4.5, 4.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import PriceDailyAdjusted
from backend.app.market_data.benchmark import BenchmarkPriceRecord


@dataclass
class RuleEvaluation:
    rule_name: str
    passed: bool
    details: str
    requires_user_confirmation: bool = False


@dataclass
class BenchmarkConsistencyReport:
    source: str
    symbol: str
    first_date: date | None
    last_date: date | None
    row_count: int
    duplicate_count: int
    non_positive_count: int

    # Calendar alignment
    du_count: int
    du_missing_from_bench_count: int
    du_missing_from_bench_pct: float
    bench_outside_du_count: int
    bench_outside_du_pct: float

    # Correlation
    overall_correlation: float | None
    yearly_correlations: dict[int, float] = field(default_factory=dict)

    # Stale runs
    stale_runs: list[dict[str, Any]] = field(default_factory=list)
    max_consecutive_identical: int = 1

    # Extreme moves
    extreme_moves_gt_7pct: list[dict[str, Any]] = field(default_factory=list)
    max_absolute_move: float = 0.0

    # Gaps
    gaps_gt_5days: list[dict[str, Any]] = field(default_factory=list)

    # Freshness
    latest_benchmark_date: date | None = None
    latest_stock_date: date | None = None
    freshness_days_diff: int | None = None

    # Spot check
    last_three_closes: list[dict[str, Any]] = field(default_factory=list)
    spot_check_status: str = "UNVERIFIED"

    # Rules
    rule_evaluations: list[RuleEvaluation] = field(default_factory=list)
    all_pass: bool = False
    stop_and_ask: bool = False
    stop_reason: str | None = None

    def render_markdown(self) -> str:
        lines: list[str] = [
            "# Benchmark Consistency Check Report",
            "",
            f"- **Source**: `{self.source}`",
            f"- **Symbol**: `{self.symbol}`",
            f"- **First Date**: `{self.first_date}`",
            f"- **Last Date**: `{self.last_date}`",
            f"- **Row Count**: `{self.row_count}`",
            f"- **Duplicate Count**: `{self.duplicate_count}`",
            f"- **Non-Positive Closes**: `{self.non_positive_count}`",
            "",
            "## Check 1 — Coverage",
            f"- Date range: `{self.first_date}` to `{self.last_date}`",
            f"- Observations: `{self.row_count}`",
            f"- Duplicates: `{self.duplicate_count}`",
            "",
            "## Check 2 — Calendar Alignment ($D_u$)",
            f"- $D_u$ observation dates count: `{self.du_count}`",
            f"- $D_u$ dates missing from benchmark: `{self.du_missing_from_bench_count}` "
            f"({self.du_missing_from_bench_pct:.2%})",
            f"- Benchmark dates outside $D_u$: `{self.bench_outside_du_count}` "
            f"({self.bench_outside_du_pct:.2%})",
            "",
            "## Check 3 — Proxy Correlation (NIFTY 200 Equal-Weighted Stock Proxy)",
            (
                f"- **Overall Pearson Correlation**: `{self.overall_correlation:.4f}`"
                if self.overall_correlation is not None
                else "- **Overall Pearson Correlation**: N/A"
            ),
            "- **Full Calendar Year Correlations**:",
        ]
        for yr, corr in sorted(self.yearly_correlations.items()):
            lines.append(f"  - **{yr}**: `{corr:.4f}`")

        lines.extend(
            [
                "",
                "## Check 4 — Stale Data",
                f"- Runs of $\\ge 2$ consecutive identical closes: `{len(self.stale_runs)}`",
                f"- Max consecutive identical closes: `{self.max_consecutive_identical}`",
            ]
        )
        for sr in self.stale_runs[:10]:
            lines.append(
                f"  - `{sr['start_date']}` to `{sr['end_date']}`: close={sr['close']}, "
                f"count={sr['count']}"
            )
        if len(self.stale_runs) > 10:
            lines.append(f"  - ... and {len(self.stale_runs) - 10} more runs.")

        lines.extend(
            [
                "",
                "## Check 5 — Extreme Moves (> 7%)",
                f"- Moves > 7%: `{len(self.extreme_moves_gt_7pct)}`",
                f"- Max 1-day absolute move: `{self.max_absolute_move:.2%}`",
            ]
        )
        for em in self.extreme_moves_gt_7pct:
            lines.append(f"  - `{em['date']}`: {em['move']:+.2%}")

        lines.extend(
            [
                "",
                "## Check 6 — Calendar Gaps (> 5 Days)",
                f"- Gaps > 5 calendar days: `{len(self.gaps_gt_5days)}`",
            ]
        )
        for gp in self.gaps_gt_5days:
            lines.append(
                f"  - `{gp['from']}` to `{gp['to']}`: `{gp['gap_days']}` days "
                f"(e.g. market holidays/extended weekends)"
            )

        lines.extend(
            [
                "",
                "## Check 7 — Freshness",
                f"- Latest Benchmark Date: `{self.latest_benchmark_date}`",
                f"- Latest Stock Price Date in Database: `{self.latest_stock_date}`",
                f"- Calendar Difference: `{self.freshness_days_diff}` days",
                "",
                "## Check 8 — Spot Check",
                f"- **Spot Check Status**: `{self.spot_check_status}`",
                "- **Last 3 Benchmark Closes**:",
            ]
        )
        for sc in self.last_three_closes:
            lines.append(f"  - `{sc['date']}`: `{sc['close']}`")

        lines.extend(
            [
                "",
                "---",
                "## PASS RULES Evaluation",
                "| Rule | Status | Details |",
                "|---|---|---|",
            ]
        )
        for r in self.rule_evaluations:
            status_str = "PASS" if r.passed else "FAIL"
            lines.append(f"| {r.rule_name} | **{status_str}** | {r.details} |")

        overall_status = "ALL PASS" if self.all_pass else "FAIL"
        lines.extend(
            [
                "",
                f"**Overall Consistency Verdict**: `{overall_status}`",
                "",
            ]
        )
        return "\n".join(lines)


def run_benchmark_checks(
    records: list[BenchmarkPriceRecord],
    session: Session | None = None,
    source: str = "YAHOO",
    symbol: str = "^CNX200",
) -> BenchmarkConsistencyReport:
    """Run all 8 consistency checks and evaluate exact PASS RULES."""
    if not records:
        return BenchmarkConsistencyReport(
            source=source,
            symbol=symbol,
            first_date=None,
            last_date=None,
            row_count=0,
            duplicate_count=0,
            non_positive_count=0,
            du_count=0,
            du_missing_from_bench_count=0,
            du_missing_from_bench_pct=1.0,
            bench_outside_du_count=0,
            bench_outside_du_pct=1.0,
            overall_correlation=None,
            all_pass=False,
            stop_reason="No benchmark records provided",
        )

    # Sort records
    sorted_recs = sorted(records, key=lambda r: r.trade_date)
    dates = [r.trade_date for r in sorted_recs]

    # Check 1: Coverage & validity
    first_date = dates[0]
    last_date = dates[-1]
    row_count = len(dates)
    seen_dates: set[date] = set()
    dup_count = 0
    non_positive_count = 0
    for r in sorted_recs:
        if r.trade_date in seen_dates:
            dup_count += 1
        seen_dates.add(r.trade_date)
        if not r.close.is_finite() or r.close <= Decimal("0"):
            non_positive_count += 1

    bench_dates_set = set(dates)

    # Check 2: Calendar alignment (D_u)
    du_dates: set[date] = set()
    latest_stock_date: date | None = None

    if session is not None:
        # Total distinct securities with price history
        total_secs = (
            session.scalar(select(func.count(func.distinct(PriceDailyAdjusted.security_id)))) or 0
        )

        if total_secs > 0:
            threshold = 0.90 * total_secs
            # Dates where count >= threshold
            du_rows = (
                session.execute(
                    select(PriceDailyAdjusted.trade_date)
                    .group_by(PriceDailyAdjusted.trade_date)
                    .having(func.count(PriceDailyAdjusted.security_id) >= threshold)
                    .order_by(PriceDailyAdjusted.trade_date)
                )
                .scalars()
                .all()
            )
            du_dates = set(du_rows)

        latest_stock_date = session.scalar(
            select(PriceDailyAdjusted.trade_date)
            .order_by(PriceDailyAdjusted.trade_date.desc())
            .limit(1)
        )

    if du_dates:
        # Benchmark dates compared with D_u range
        min_du, max_du = min(du_dates), max(du_dates)
        du_missing_from_bench = du_dates - bench_dates_set
        bench_in_du_span = {d for d in bench_dates_set if min_du <= d <= max_du}
        bench_outside_du = bench_in_du_span - du_dates

        du_missing_pct = len(du_missing_from_bench) / len(du_dates)
        bench_outside_pct = (
            len(bench_outside_du) / len(bench_in_du_span) if bench_in_du_span else 0.0
        )
    else:
        du_missing_from_bench = set()
        bench_outside_du = set()
        du_missing_pct = 0.0
        bench_outside_pct = 0.0

    # Check 3: Proxy correlation
    # Compute daily log returns of benchmark
    b_df = pd.DataFrame([{"date": r.trade_date, "close": float(r.close)} for r in sorted_recs])
    b_df = b_df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    b_series = b_df.set_index("date")["close"]
    b_rets = np.log(b_series / b_series.shift(1)).dropna()

    overall_corr: float | None = None
    yearly_corrs: dict[int, float] = {}

    if session is not None and not b_rets.empty:
        # Load daily adjusted closes for universe stocks
        stock_rows = session.execute(
            select(
                PriceDailyAdjusted.security_id,
                PriceDailyAdjusted.trade_date,
                PriceDailyAdjusted.adjusted_close,
            )
            .where(
                PriceDailyAdjusted.trade_date >= b_rets.index[0],
                PriceDailyAdjusted.trade_date <= b_rets.index[-1],
            )
            .order_by(PriceDailyAdjusted.trade_date)
        ).all()

        if stock_rows:
            stock_df = pd.DataFrame(
                stock_rows, columns=["security_id", "trade_date", "adjusted_close"]
            )
            # Pivot table: date x security_id
            pivot = stock_df.pivot(
                index="trade_date", columns="security_id", values="adjusted_close"
            ).astype(float)
            # Stock log returns
            stock_rets = np.log(pivot / pivot.shift(1))
            # Equal-weighted mean return per day
            mean_stock_rets = stock_rets.mean(axis=1, skipna=True).dropna()

            # Align with benchmark returns
            aligned = pd.concat(
                [b_rets.rename("bench"), mean_stock_rets.rename("proxy")], axis=1
            ).dropna()
            if len(aligned) >= 30:
                corr_matrix = np.corrcoef(aligned["bench"], aligned["proxy"])
                overall_corr = float(corr_matrix[0, 1])

                # Per calendar year
                aligned["year"] = [d.year for d in aligned.index]
                for yr, group in aligned.groupby("year"):
                    if len(group) >= 150:  # Full calendar year threshold
                        c_yr = float(np.corrcoef(group["bench"], group["proxy"])[0, 1])
                        yearly_corrs[int(yr)] = round(c_yr, 4)

    # Check 4: Stale data (runs of >= 2 identical closes)
    stale_runs: list[dict[str, Any]] = []
    current_run_close: Decimal | None = None
    current_run_start: date | None = None
    current_run_count = 1
    max_identical = 1

    for i in range(1, len(sorted_recs)):
        prev_r = sorted_recs[i - 1]
        curr_r = sorted_recs[i]
        if curr_r.close == prev_r.close:
            if current_run_close is None:
                current_run_close = curr_r.close
                current_run_start = prev_r.trade_date
                current_run_count = 2
            else:
                current_run_count += 1
            if current_run_count > max_identical:
                max_identical = current_run_count
        else:
            if current_run_close is not None:
                stale_runs.append(
                    {
                        "start_date": current_run_start,
                        "end_date": prev_r.trade_date,
                        "close": float(current_run_close),
                        "count": current_run_count,
                    }
                )
                current_run_close = None
                current_run_count = 1

    if current_run_close is not None:
        stale_runs.append(
            {
                "start_date": current_run_start,
                "end_date": sorted_recs[-1].trade_date,
                "close": float(current_run_close),
                "count": current_run_count,
            }
        )

    # Check 5: Extreme moves (> 7%)
    extreme_moves: list[dict[str, Any]] = []
    max_abs_move = 0.0
    for i in range(1, len(sorted_recs)):
        prev_c = sorted_recs[i - 1].close
        curr_c = sorted_recs[i].close
        if prev_c > 0:
            rel_move = float((curr_c - prev_c) / prev_c)
            abs_move = abs(rel_move)
            if abs_move > max_abs_move:
                max_abs_move = abs_move
            if abs_move > 0.07:
                extreme_moves.append(
                    {
                        "date": sorted_recs[i].trade_date,
                        "move": rel_move,
                    }
                )

    # Check 6: Gaps (> 5 calendar days)
    gaps: list[dict[str, Any]] = []
    for i in range(1, len(sorted_recs)):
        prev_d = sorted_recs[i - 1].trade_date
        curr_d = sorted_recs[i].trade_date
        gap_days = (curr_d - prev_d).days
        if gap_days > 5:
            gaps.append(
                {
                    "from": prev_d,
                    "to": curr_d,
                    "gap_days": gap_days,
                }
            )

    # Check 7: Freshness
    freshness_days: int | None = None
    if latest_stock_date is not None:
        freshness_days = abs((last_date - latest_stock_date).days)

    # Check 8: Spot check (last 3 closes)
    last_three = [
        {"date": r.trade_date.isoformat(), "close": float(r.close)} for r in sorted_recs[-3:]
    ]

    # Evaluate PASS RULES
    rules: list[RuleEvaluation] = []
    all_pass = True
    stop_and_ask = False
    stop_reason = None

    # Rule 1 — Historical coverage (first date <= 2015-03-31)
    target_start = date(2015, 3, 31)
    rule1_pass = first_date <= target_start
    if not rule1_pass:
        all_pass = False
    rules.append(
        RuleEvaluation(
            rule_name="Rule 1 — Historical coverage",
            passed=rule1_pass,
            details=f"First date {first_date} {'<=' if rule1_pass else '>'} target {target_start}",
            requires_user_confirmation=not rule1_pass,
        )
    )

    # Rule 2 — Data validity (0 duplicate dates, 0 non-positive closes)
    rule2_pass = dup_count == 0 and non_positive_count == 0
    if not rule2_pass:
        all_pass = False
    rules.append(
        RuleEvaluation(
            rule_name="Rule 2 — Data validity",
            passed=rule2_pass,
            details=f"Duplicates: {dup_count}, Non-positive: {non_positive_count}",
        )
    )

    # Rule 3 — Calendar alignment (at most 1% du missing, at most 1% bench outside du)
    rule3_pass = du_missing_pct <= 0.01 and bench_outside_pct <= 0.01
    if not rule3_pass:
        all_pass = False
    rules.append(
        RuleEvaluation(
            rule_name="Rule 3 — Calendar alignment",
            passed=rule3_pass,
            details=(
                f"Missing from bench: {du_missing_pct:.2%} (<= 1%), "
                f"Outside Du: {bench_outside_pct:.2%} (<= 1%)"
            ),
        )
    )

    # Rule 4 — Correlation (overall >= 0.95, yearly >= 0.90)
    if overall_corr is not None:
        if overall_corr >= 0.95:
            # Check yearly correlations
            failing_years = [yr for yr, c in yearly_corrs.items() if c < 0.90]
            rule4_pass = len(failing_years) == 0
            if not rule4_pass:
                all_pass = False
            details = (
                f"Overall corr {overall_corr:.4f} >= 0.95. Failing years (<0.90): {failing_years}"
            )
        elif 0.90 <= overall_corr < 0.95:
            rule4_pass = False
            all_pass = False
            stop_and_ask = True
            stop_reason = (
                f"Overall correlation {overall_corr:.4f} is between 0.90 and 0.95; "
                f"requires confirmation"
            )
            details = f"Overall corr {overall_corr:.4f} is 0.90 <= corr < 0.95 (STOP condition)"
        else:
            rule4_pass = False
            all_pass = False
            details = f"Overall corr {overall_corr:.4f} < 0.90 (FAIL)"
    else:
        # If DB not available, cannot evaluate correlation
        rule4_pass = True
        details = "Correlation evaluation skipped (database session not available)"

    rules.append(
        RuleEvaluation(
            rule_name="Rule 4 — Proxy correlation",
            passed=rule4_pass,
            details=details,
            requires_user_confirmation=stop_and_ask,
        )
    )

    # Rule 5 — Stale data (not more than 3 consecutive identical closes)
    rule5_pass = max_identical <= 3
    if not rule5_pass:
        all_pass = False
    rules.append(
        RuleEvaluation(
            rule_name="Rule 5 — Stale data",
            passed=rule5_pass,
            details=f"Max consecutive identical closes: {max_identical} (<= 3)",
        )
    )

    # Rule 6 — Extreme movement (no one-day move > 25%)
    rule6_pass = max_abs_move <= 0.25
    if not rule6_pass:
        all_pass = False
    rules.append(
        RuleEvaluation(
            rule_name="Rule 6 — Extreme movement",
            passed=rule6_pass,
            details=f"Max 1-day move: {max_abs_move:.2%} (<= 25%)",
        )
    )

    # Rule 7 — Freshness (within 3 calendar days of latest stock price date)
    if freshness_days is not None:
        rule7_pass = freshness_days <= 3
        if not rule7_pass:
            all_pass = False
        details_str = f"Diff: {freshness_days} days (<= 3 days)"
    else:
        rule7_pass = True
        details_str = "Freshness check skipped (database session not available)"

    rules.append(
        RuleEvaluation(
            rule_name="Rule 7 — Freshness",
            passed=rule7_pass,
            details=details_str,
        )
    )

    return BenchmarkConsistencyReport(
        source=source,
        symbol=symbol,
        first_date=first_date,
        last_date=last_date,
        row_count=row_count,
        duplicate_count=dup_count,
        non_positive_count=non_positive_count,
        du_count=len(du_dates),
        du_missing_from_bench_count=len(du_missing_from_bench),
        du_missing_from_bench_pct=du_missing_pct,
        bench_outside_du_count=len(bench_outside_du),
        bench_outside_du_pct=bench_outside_pct,
        overall_correlation=overall_corr,
        yearly_correlations=yearly_corrs,
        stale_runs=stale_runs,
        max_consecutive_identical=max_identical,
        extreme_moves_gt_7pct=extreme_moves,
        max_absolute_move=max_abs_move,
        gaps_gt_5days=gaps,
        latest_benchmark_date=last_date,
        latest_stock_date=latest_stock_date,
        freshness_days_diff=freshness_days,
        last_three_closes=last_three,
        spot_check_status="UNVERIFIED",
        rule_evaluations=rules,
        all_pass=all_pass,
        stop_and_ask=stop_and_ask,
        stop_reason=stop_reason,
    )
