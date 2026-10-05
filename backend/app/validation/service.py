"""Point-in-time historical score validation, persistence, and read services."""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from statistics import mean
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ExperimentLog,
    ModelConfig,
    PriceDailyAdjusted,
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    SectorDivergenceRun,
    SectorDivergenceScore,
    StockRiskResult,
    ValidationResult,
    ValidationRun,
)
from backend.app.risk_score.service import run_stock_score_calculation
from backend.app.validation.metrics import (
    confidence_calibration,
    construct_forward_targets,
    cross_section_metrics,
    layer1_band_rates,
    spearman_rank_correlation,
)
from backend.app.validation.schemas import (
    ValidationResultOut,
    ValidationRunDetailOut,
    ValidationRunSummaryOut,
)
from backend.app.validation.splits import walk_forward_splits

SURVIVORSHIP_WARNING = (
    "Historical validation uses current NIFTY 200 membership only; results contain "
    "survivorship bias and must not be presented as investable backtests."
)

TARGET_KEYS = (
    "forward_realised_volatility_20d",
    "forward_max_drawdown_20d",
    "forward_worst_5d_return",
)


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def monthly_as_of_dates(session: Session, start: date, end: date) -> list[date]:
    """Return last available adjusted-price session in each calendar month."""
    dates = session.scalars(
        select(PriceDailyAdjusted.trade_date)
        .where(PriceDailyAdjusted.trade_date.between(start, end))
        .distinct()
        .order_by(PriceDailyAdjusted.trade_date)
    ).all()
    monthly: dict[tuple[int, int], date] = {}
    for trade_date in dates:
        monthly[(trade_date.year, trade_date.month)] = trade_date
    return list(monthly.values())


def backfill_monthly_scores(
    session: Session,
    start: date,
    end: date,
    *,
    score_config_version: str = "1.0.0",
) -> list[UUID]:
    """Create/reuse monthly point-in-time scores with the survivorship warning."""
    run_ids: list[UUID] = []
    for as_of in monthly_as_of_dates(session, start, end):
        cutoff = datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)
        summary = run_stock_score_calculation(
            session,
            as_of,
            cutoff,
            config_version=score_config_version,
            result_limitations=[SURVIVORSHIP_WARNING],
        )
        run_ids.append(summary.run_id)
    return run_ids


def _target_values(targets: object) -> dict[str, float]:
    from backend.app.validation.metrics import ForwardTargets

    if not isinstance(targets, ForwardTargets):
        raise TypeError("targets must be ForwardTargets")
    return {
        TARGET_KEYS[0]: targets.realised_volatility_20d,
        TARGET_KEYS[1]: targets.max_drawdown_20d,
        TARGET_KEYS[2]: targets.worst_5d_return,
    }


def _load_observations(
    session: Session,
    runs: Sequence[ScoreRun],
    *,
    horizon: int,
    worst_window: int,
    random_seed: int,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for run in runs:
        results = session.scalars(
            select(StockRiskResult).where(StockRiskResult.run_id == run.id)
        ).all()
        if not results:
            continue
        security_ids = [row.security_id for row in results]
        price_rows = session.scalars(
            select(PriceDailyAdjusted)
            .where(
                PriceDailyAdjusted.security_id.in_(security_ids),
                PriceDailyAdjusted.trade_date >= run.as_of_date,
                PriceDailyAdjusted.trade_date
                <= run.as_of_date + timedelta(days=max(60, horizon * 4)),
            )
            .order_by(
                PriceDailyAdjusted.security_id,
                PriceDailyAdjusted.trade_date,
                PriceDailyAdjusted.computed_at,
            )
        ).all()
        prices: dict[UUID, dict[date, float]] = defaultdict(dict)
        for row in price_rows:
            prices[row.security_id][row.trade_date] = float(row.adjusted_close)

        component_rows = session.scalars(
            select(ScoreComponentValue).where(
                ScoreComponentValue.run_id == run.id,
                ScoreComponentValue.component_id.in_(["ewma_volatility", "beta_to_benchmark"]),
            )
        ).all()
        component_points = {
            (row.security_id, row.component_id): (
                float(row.points) if row.points is not None else None
            )
            for row in component_rows
        }
        for result in results:
            target = construct_forward_targets(
                sorted(prices[result.security_id].items()),
                run.as_of_date,
                horizon=horizon,
                worst_window=worst_window,
            )
            if target is None:
                continue
            generator = random.Random(f"{random_seed}:{run.as_of_date}:{result.symbol}")
            observations.append(
                {
                    "period": run.as_of_date.isoformat(),
                    "security_id": result.security_id,
                    "symbol": result.symbol,
                    "score": float(result.total_score),
                    "confidence": float(result.confidence),
                    "targets": _target_values(target),
                    "baselines": {
                        "trailing_volatility": component_points.get(
                            (result.security_id, "ewma_volatility")
                        ),
                        "beta": component_points.get((result.security_id, "beta_to_benchmark")),
                        "random": generator.random() * 100.0,
                    },
                }
            )
    return observations


def _mean_period_spearman(
    observations: list[dict[str, Any]],
    target_key: str,
    minimum_cross_section: int,
) -> float | None:
    """Average cross-sectional rank correlation across evaluation periods."""
    by_period: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        by_period[str(row["period"])].append(row)
    correlations: list[float] = []
    for rows in by_period.values():
        if len(rows) < minimum_cross_section:
            continue
        correlation = spearman_rank_correlation(
            [float(row["score"]) for row in rows],
            [float(row["targets"][target_key]) for row in rows],
        )
        if correlation is not None:
            correlations.append(correlation)
    return mean(correlations) if correlations else None


def _persist_result(
    session: Session,
    run_id: UUID,
    metric_key: str,
    component_key: str,
    value: float | None,
    baseline_value: float | None,
    n: int,
    period: str,
) -> None:
    session.add(
        ValidationResult(
            id=uuid4(),
            run_id=run_id,
            metric_key=metric_key,
            component_key=component_key,
            value=value,
            baseline_value=baseline_value,
            n=n,
            period=period,
        )
    )


def _aggregate_validation_metrics(
    session: Session,
    validation_run_id: UUID,
    observations: list[dict[str, Any]],
    confidence_bins: list[float],
    minimum_cross_section: int,
) -> list[str]:
    failures: list[str] = []
    by_period: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for observation in observations:
        by_period[str(observation["period"])].append(observation)

    excluded_periods = [
        period for period, rows in by_period.items() if len(rows) < minimum_cross_section
    ]
    by_period = {
        period: rows for period, rows in by_period.items() if len(rows) >= minimum_cross_section
    }
    if excluded_periods:
        failures.append(
            f"Excluded {len(excluded_periods)} period(s) below the configured "
            f"minimum cross-section of {minimum_cross_section}."
        )

    for target_key in TARGET_KEYS:
        period_values: dict[str, dict[str, float | None]] = {}
        baseline_correlations: dict[str, list[float]] = {
            "trailing_volatility": [],
            "beta": [],
            "random": [],
        }
        for period, rows in sorted(by_period.items()):
            scores = [float(row["score"]) for row in rows]
            targets = [float(row["targets"][target_key]) for row in rows]
            metrics = cross_section_metrics(scores, targets)
            period_values[period] = metrics
            for metric_key, value in metrics.items():
                _persist_result(
                    session,
                    validation_run_id,
                    f"{metric_key}:{target_key}",
                    "score",
                    value,
                    None,
                    len(rows),
                    period,
                )
            for baseline in ("trailing_volatility", "beta", "random"):
                pairs = [
                    (float(row["baselines"][baseline]), float(row["targets"][target_key]))
                    for row in rows
                    if row["baselines"][baseline] is not None
                ]
                correlation = (
                    spearman_rank_correlation(
                        [pair[0] for pair in pairs], [pair[1] for pair in pairs]
                    )
                    if pairs
                    else None
                )
                if correlation is not None:
                    baseline_correlations[baseline].append(correlation)
                _persist_result(
                    session,
                    validation_run_id,
                    f"spearman:{target_key}",
                    f"baseline_{baseline}",
                    correlation,
                    None,
                    len(pairs),
                    period,
                )

        valid_score_correlations = [
            float(metrics["spearman"])
            for metrics in period_values.values()
            if metrics["spearman"] is not None
        ]
        aggregate_score = mean(valid_score_correlations) if valid_score_correlations else None
        _persist_result(
            session,
            validation_run_id,
            f"mean_spearman:{target_key}",
            "score",
            aggregate_score,
            None,
            sum(len(rows) for rows in by_period.values()),
            "all",
        )
        reverse = target_key == "forward_worst_5d_return"
        oriented_score = (
            -aggregate_score
            if reverse and aggregate_score is not None
            else aggregate_score
        )
        for baseline, correlations in baseline_correlations.items():
            baseline_value = mean(correlations) if correlations else None
            oriented_baseline = (
                -baseline_value if reverse and baseline_value is not None else baseline_value
            )
            beat = (
                1.0
                if oriented_score is not None
                and oriented_baseline is not None
                and oriented_score > oriented_baseline
                else 0.0
            )
            if beat == 0.0:
                failures.append(f"Score did not beat {baseline} for {target_key}.")
            _persist_result(
                session,
                validation_run_id,
                f"beats_baseline:{target_key}",
                baseline,
                beat,
                baseline_value,
                len(valid_score_correlations),
                "all",
            )

        calibration_rows = [
            (float(row["score"]), float(row["confidence"]), float(row["targets"][target_key]))
            for row in observations
        ]
        calibration = confidence_calibration(
            calibration_rows, confidence_bins, reverse_target=reverse
        )
        populated_errors: list[tuple[float, float]] = []
        for item in calibration:
            key = f"confidence_{item['lower']:g}_{item['upper']:g}"
            _persist_result(
                session,
                validation_run_id,
                f"calibration_spearman:{target_key}",
                key,
                item["spearman"] if isinstance(item["spearman"], float) else None,
                None,
                int(item["n"]),
                "all",
            )
            error = item["rank_error"] if isinstance(item["rank_error"], float) else None
            _persist_result(
                session,
                validation_run_id,
                f"calibration_rank_error:{target_key}",
                key,
                error,
                None,
                int(item["n"]),
                "all",
            )
            if error is not None:
                populated_errors.append((float(item["lower"]), error))
        if len(populated_errors) >= 2 and populated_errors[-1][1] >= populated_errors[0][1]:
            failures.append(f"High confidence was not more reliable for {target_key}.")
    return failures


def _persist_stability(
    session: Session, validation_run_id: UUID, observations: list[dict[str, Any]]
) -> None:
    by_period: dict[str, dict[str, float]] = defaultdict(dict)
    for row in observations:
        by_period[str(row["period"])][str(row["symbol"])] = float(row["score"])
    periods = sorted(by_period)
    for prior, current in zip(periods[:-1], periods[1:], strict=True):
        common = sorted(set(by_period[prior]) & set(by_period[current]))
        value = spearman_rank_correlation(
            [by_period[prior][symbol] for symbol in common],
            [by_period[current][symbol] for symbol in common],
        )
        _persist_result(
            session,
            validation_run_id,
            "score_rank_stability",
            "score",
            value,
            None,
            len(common),
            f"{prior}->{current}",
        )


def _persist_layer1_bands(
    session: Session,
    validation_run_id: UUID,
    start: date,
    end: date,
    bands: list[float],
) -> None:
    horizons = session.scalars(
        select(SectorDivergenceScore.horizon)
        .join(SectorDivergenceRun, SectorDivergenceScore.run_id == SectorDivergenceRun.id)
        .where(SectorDivergenceRun.signal_date.between(start, end))
        .distinct()
        .order_by(SectorDivergenceScore.horizon)
    ).all()
    for horizon in horizons:
        values = [
            float(value)
            for value in session.scalars(
                select(SectorDivergenceScore.divergence_value)
                .join(SectorDivergenceRun, SectorDivergenceScore.run_id == SectorDivergenceRun.id)
                .where(
                    SectorDivergenceRun.signal_date.between(start, end),
                    SectorDivergenceScore.horizon == horizon,
                )
            ).all()
        ]
        for band, rate in layer1_band_rates(values, bands).items():
            _persist_result(
                session,
                validation_run_id,
                f"layer1_exceedance_{band:g}_sigma",
                f"horizon_{horizon}",
                rate,
                math.erfc(band / math.sqrt(2.0)),
                len(values),
                f"{start.isoformat()}:{end.isoformat()}",
            )


def run_validation(
    session: Session,
    start: date,
    end: date,
    *,
    score_config_version: str = "1.0.0",
    validation_config_version: str = "1.0.0",
    run_ablation: bool = True,
) -> ValidationRunDetailOut:
    """Validate historical scores, persist failures, and reuse an identical run."""
    config_row = session.scalars(
        select(ModelConfig).where(
            ModelConfig.config_key == "validation_parameters",
            ModelConfig.version == validation_config_version,
        )
    ).first()
    if config_row is None:
        raise ValueError("validation configuration is not installed")
    score_config = session.scalars(
        select(ModelConfig).where(
            ModelConfig.config_key == "risk_engine_parameters",
            ModelConfig.version == score_config_version,
        )
    ).first()
    if score_config is None:
        raise ValueError("score configuration is not installed")
    definitions = session.scalars(
        select(ScoreComponentDefinition).where(ScoreComponentDefinition.active.is_(True))
    ).all()
    config: dict[str, Any] = dict(config_row.configuration)
    effective_config = {
        **config,
        "score_config_version": score_config_version,
        "score_config_fingerprint": score_config.configuration_hash,
        "validation_config_fingerprint": config_row.configuration_hash,
        "active_components": [
            {
                "component_id": definition.component_id,
                "dimension": definition.dimension,
                "weight": float(definition.weight),
            }
            for definition in sorted(definitions, key=lambda item: item.component_id)
        ],
        "run_ablation": run_ablation,
    }
    fingerprint = _canonical_hash(effective_config)
    period = f"{start.isoformat()}:{end.isoformat()}"
    existing = session.scalars(
        select(ValidationRun).where(
            ValidationRun.kind == "historical_score_validation",
            ValidationRun.config_fingerprint == fingerprint,
            ValidationRun.period == period,
        )
    ).first()
    if existing is not None:
        return get_validation_run(session, existing.id)

    now = datetime.now(UTC)
    run = ValidationRun(
        id=uuid4(),
        kind="historical_score_validation",
        config_fingerprint=fingerprint,
        period=period,
        started_at=now,
        completed_at=None,
        notes={},
    )
    session.add(run)
    session.flush()

    base_configuration = dict(score_config.configuration)
    base_configuration["ablation"] = {
        "excluded_components": [],
        "excluded_dimensions": [],
    }
    base_config_fingerprint = _canonical_hash(base_configuration)
    base_runs = session.scalars(
        select(ScoreRun)
        .where(
            ScoreRun.as_of_date.between(start, end),
            ScoreRun.status == "completed",
            ScoreRun.config_version == score_config_version,
            ScoreRun.config_fingerprint == base_config_fingerprint,
        )
        .order_by(ScoreRun.as_of_date)
    ).all()
    monthly_dates = sorted({row.as_of_date for row in base_runs})
    minimum_periods = (
        int(config["walk_forward_min_train_periods"])
        + int(config["walk_forward_embargo_periods"])
        + int(config["walk_forward_test_periods"])
    )
    folds = (
        list(
            walk_forward_splits(
                monthly_dates,
                min_train=int(config["walk_forward_min_train_periods"]),
                test_len=int(config["walk_forward_test_periods"]),
                step=int(config["walk_forward_step_periods"]),
                embargo=int(config["walk_forward_embargo_periods"]),
            )
        )
        if len(monthly_dates) >= minimum_periods
        else []
    )
    evaluation_dates = {
        monthly_dates[index] for _, test_indices in folds for index in test_indices
    }
    evaluation_runs = [row for row in base_runs if row.as_of_date in evaluation_dates]
    observations = _load_observations(
        session,
        evaluation_runs,
        horizon=int(config["target_horizon_trading_days"]),
        worst_window=int(config["worst_return_window_days"]),
        random_seed=int(config["random_seed"]),
    )

    failures = _aggregate_validation_metrics(
        session,
        run.id,
        observations,
        [float(value) for value in config["confidence_bin_edges"]],
        int(config["minimum_cross_section"]),
    )
    _persist_stability(session, run.id, observations)
    _persist_layer1_bands(
        session,
        run.id,
        start,
        end,
        [float(value) for value in config["layer1_sigma_bands"]],
    )

    _persist_result(
        session, run.id, "walk_forward_fold_count", "score", float(len(folds)), None,
        len(monthly_dates), period
    )

    variants: list[object] = [
        "full_score",
        "baseline_trailing_volatility",
        "baseline_beta",
        "baseline_random",
    ]
    ablation_recommendations: dict[str, str] = {}
    if run_ablation and evaluation_runs:
        variants.extend(
            f"exclude_component:{definition.component_id}" for definition in definitions
        )
        variants.extend(
            f"exclude_dimension:{dimension}"
            for dimension in sorted({definition.dimension for definition in definitions})
        )
        # The job records all trials. Each ablation score run is fingerprinted and idempotent.
        for variant in variants[4:]:
            prefix, key = str(variant).split(":", maxsplit=1)
            variant_runs: list[ScoreRun] = []
            for base_run in evaluation_runs:
                summary = run_stock_score_calculation(
                    session,
                    base_run.as_of_date,
                    base_run.data_cutoff,
                    config_version=score_config_version,
                    exclude_components={key} if prefix == "exclude_component" else None,
                    exclude_dimensions={key} if prefix == "exclude_dimension" else None,
                    result_limitations=[SURVIVORSHIP_WARNING],
                )
                scored_run = session.get(ScoreRun, summary.run_id)
                if scored_run is not None:
                    variant_runs.append(scored_run)
            variant_observations = _load_observations(
                session,
                variant_runs,
                horizon=int(config["target_horizon_trading_days"]),
                worst_window=int(config["worst_return_window_days"]),
                random_seed=int(config["random_seed"]),
            )
            oriented_deltas: list[float] = []
            for target_key in TARGET_KEYS:
                full_correlation = _mean_period_spearman(
                    observations,
                    target_key,
                    int(config["minimum_cross_section"]),
                )
                variant_correlation = _mean_period_spearman(
                    variant_observations,
                    target_key,
                    int(config["minimum_cross_section"]),
                )
                delta = (
                    variant_correlation - full_correlation
                    if variant_correlation is not None and full_correlation is not None
                    else None
                )
                if target_key == "forward_worst_5d_return" and delta is not None:
                    delta = -delta
                if delta is not None:
                    oriented_deltas.append(delta)
                _persist_result(
                    session,
                    run.id,
                    f"ablation_delta_spearman:{target_key}",
                    str(variant),
                    delta,
                    full_correlation,
                    len(variant_observations),
                    "all",
                )
            if oriented_deltas:
                mean_delta = mean(oriented_deltas)
                ablation_recommendations[str(variant)] = (
                    "keep" if mean_delta < 0.0 else "does_not_help"
                )

    session.add(
        ExperimentLog(
            id=uuid4(),
            created_at=datetime.now(UTC),
            description=(
                "Step 13 descriptive-risk validation. No trading strategy metric was computed; "
                "trial-count adjustment is therefore not applicable."
            ),
            variants_tried=variants,
            config_fingerprint=fingerprint,
        )
    )
    if not observations:
        failures.append("No valid forward labels were available; score meaning is unproven.")
    run.notes = {
        "status": "failed" if failures else "completed",
        "failures": failures,
        "score_run_count": len(base_runs),
        "evaluation_score_run_count": len(evaluation_runs),
        "walk_forward_fold_count": len(folds),
        "labelled_observation_count": len(observations),
        "ablation_recommendations": ablation_recommendations,
        "survivorship_warning": str(config.get("survivorship_warning", SURVIVORSHIP_WARNING)),
        "limitations": list(config.get("limitations", [])),
        "method_version": "historical-score-validation-v1",
        "multiple_testing": "All variants logged; no trading-style metric shown.",
    }
    run.completed_at = datetime.now(UTC)
    session.commit()
    return get_validation_run(session, run.id)


def _summary(row: ValidationRun) -> ValidationRunSummaryOut:
    notes = dict(row.notes or {})
    return ValidationRunSummaryOut(
        id=row.id,
        kind=row.kind,
        config_fingerprint=row.config_fingerprint,
        period=row.period,
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=str(notes.get("status", "running")),
        notes=notes,
    )


def list_validation_runs(session: Session) -> list[ValidationRunSummaryOut]:
    rows = session.scalars(
        select(ValidationRun).order_by(desc(ValidationRun.started_at))
    ).all()
    return [_summary(row) for row in rows]


def get_validation_run(session: Session, run_id: UUID) -> ValidationRunDetailOut:
    row = session.get(ValidationRun, run_id)
    if row is None:
        raise KeyError(str(run_id))
    results = session.scalars(
        select(ValidationResult)
        .where(ValidationResult.run_id == run_id)
        .order_by(
            ValidationResult.metric_key,
            ValidationResult.component_key,
            ValidationResult.period,
        )
    ).all()
    summary = _summary(row)
    return ValidationRunDetailOut(
        **summary.model_dump(),
        results=[ValidationResultOut.model_validate(result) for result in results],
    )
