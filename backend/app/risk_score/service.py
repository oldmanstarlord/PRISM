"""Orchestration, synthesis, persistence, and queries for PRISM stock risk scores (D1-D6)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    AuditLog,
    ConfidenceFactorValue,
    ModelConfig,
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    Security,
    SecurityAlias,
    StockRiskResult,
)
from backend.app.risk_score.components.base import ComponentValue, RiskContext
from backend.app.risk_score.confidence import ConfidenceEngine
from backend.app.risk_score.registry import (
    registry,
)
from backend.app.risk_score.scorer import RiskScorer


def _canonical_hash(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 fingerprint for a JSON-serializable dictionary."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_input_fingerprint(
    universe: list[tuple[UUID, str, str]],
    as_of: date,
    data_cutoff: datetime,
) -> str:
    """Compute point-in-time input fingerprint for idempotency checking (D6)."""
    payload = {
        "as_of": as_of.isoformat(),
        "data_cutoff": data_cutoff.isoformat(),
        "universe": [(str(u[0]), u[1], u[2]) for u in universe],
    }
    return _canonical_hash(payload)


@dataclass
class CalculationSummary:
    """Result summary of a stock risk score calculation run."""

    run_id: UUID
    is_new: bool
    as_of_date: date
    total_securities: int
    scored_securities: int
    config_version: str
    config_fingerprint: str
    input_fingerprint: str


def run_stock_score_calculation(
    session: Session,
    as_of: date,
    data_cutoff: datetime | None = None,
    config_version: str = "1.0.0",
    force: bool = False,
) -> CalculationSummary:
    """Orchestrate dynamic component execution, synthesis, and persistence (D1-D6)."""
    now = datetime.now(UTC)
    cutoff = data_cutoff or datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)

    # 1. Load active universe of securities joined with valid alias
    rows = session.execute(
        select(Security.id, SecurityAlias.symbol, Security.industry)
        .join(SecurityAlias, SecurityAlias.security_id == Security.id)
        .where(
            Security.is_active == True,  # noqa: E712
            SecurityAlias.valid_from <= as_of,
            (SecurityAlias.valid_to == None) | (SecurityAlias.valid_to >= as_of),  # noqa: E711
        )
        .order_by(SecurityAlias.symbol)
    ).all()

    if not rows:
        # Fallback to all securities if none flagged active or aliased in period
        rows = session.execute(
            select(Security.id, SecurityAlias.symbol, Security.industry)
            .join(SecurityAlias, SecurityAlias.security_id == Security.id)
            .order_by(SecurityAlias.symbol)
        ).all()

    universe = [(r[0], r[1], r[2] or "General") for r in rows]

    # 2. Load model configuration (D1)
    cfg_row = session.scalars(
        select(ModelConfig)
        .where(
            ModelConfig.config_key == "risk_engine_parameters",
            ModelConfig.version == config_version,
        )
        .order_by(desc(ModelConfig.created_at))
        .limit(1)
    ).first()

    if cfg_row is not None:
        config_data = dict(cfg_row.configuration)
        cfg_id = cfg_row.id
    else:
        # Fallback config
        config_data = {
            "ewma_lambda": 0.94,
            "volatility_annualisation_factor": 252,
            "beta_lookback_days": 250,
            "drawdown_lookback_days": 250,
            "tail_loss_lookback_days": 250,
            "tail_loss_alpha": 0.05,
            "adv_lookback_days": 20,
            "zero_volume_lookback_days": 60,
            "sector_divergence_horizon": 20,
            "min_coverage_ratio": 0.70,
            "min_industry_group_size": 5,
        }
        cfg_id = uuid4()

    config_fingerprint = _canonical_hash(config_data)
    input_fingerprint = compute_input_fingerprint(universe, as_of, cutoff)

    # 3. Check for existing completed run (D6 Idempotency)
    existing_run = session.scalars(
        select(ScoreRun)
        .where(
            ScoreRun.as_of_date == as_of,
            ScoreRun.config_fingerprint == config_fingerprint,
            ScoreRun.input_fingerprint == input_fingerprint,
            ScoreRun.status == "completed",
        )
        .order_by(desc(ScoreRun.completed_at))
        .limit(1)
    ).first()

    if existing_run is not None and not force:
        return CalculationSummary(
            run_id=existing_run.id,
            is_new=False,
            as_of_date=existing_run.as_of_date,
            total_securities=existing_run.total_securities,
            scored_securities=existing_run.scored_securities,
            config_version=existing_run.config_version,
            config_fingerprint=existing_run.config_fingerprint,
            input_fingerprint=existing_run.input_fingerprint,
        )

    # 4. Synchronize registry with database definitions (D2)
    registry.load_from_db(session)
    active_defs = {c.component_id: c for c in registry.list_components(active_only=True)}

    # 5. Execute all active components point-in-time
    context = RiskContext(
        session=session,
        as_of=as_of,
        data_cutoff=cutoff,
        config=config_data,
    )

    component_values_by_key: dict[str, list[ComponentValue]] = {}
    for comp_id in active_defs.keys():
        handler = registry.get_instance(comp_id)
        if handler is not None and hasattr(handler, "compute"):
            vals = handler.compute(as_of, universe, context)
            component_values_by_key[comp_id] = vals

    # 6. Scorer engine synthesis (Percentile ranking, weighting, renormalisation)
    scorer = RiskScorer(config_data, active_defs)
    risk_scores = scorer.synthesize(universe, component_values_by_key)

    # 7. Confidence engine evaluation (6 factors and hard caps)
    confidence_engine = ConfidenceEngine(config_data)
    confidence_results = confidence_engine.evaluate(risk_scores, context)

    # 8. Persist Run and Results (Atomic Transaction)
    run_id = uuid4()
    score_run = ScoreRun(
        id=run_id,
        as_of_date=as_of,
        data_cutoff=cutoff,
        model_config_id=cfg_id,
        config_version=config_version,
        config_fingerprint=config_fingerprint,
        input_fingerprint=input_fingerprint,
        status="completed",
        total_securities=len(universe),
        scored_securities=len(risk_scores),
        started_at=now,
        completed_at=datetime.now(UTC),
    )
    session.add(score_run)
    session.flush()

    # Persist StockRiskResult rows
    for sec_id, score_obj in risk_scores.items():
        conf_obj = confidence_results.get(sec_id)
        final_conf = conf_obj.final_confidence if conf_obj else 50.0

        dim_scores_json = {
            dim: {
                "score": d.score,
                "weight": d.weight,
                "status": d.status,
            }
            for dim, d in score_obj.dimensions.items()
        }

        res = StockRiskResult(
            id=uuid4(),
            run_id=run_id,
            security_id=sec_id,
            symbol=score_obj.symbol,
            total_score=Decimal(str(score_obj.overall_score)),
            confidence=Decimal(str(final_conf)),
            data_coverage=Decimal(str(score_obj.coverage)),
            dimension_scores=dim_scores_json,
            top_reasons=score_obj.top_reasons,
            limitations=score_obj.limitations,
            computed_at=datetime.now(UTC),
        )
        session.add(res)

    # Persist ScoreComponentValue rows
    for comp_id, cv_list in component_values_by_key.items():
        for cv in cv_list:
            # Match scored component for percentile and points
            sc_list = risk_scores[cv.security_id].components
            matched_sc = next((c for c in sc_list if c.component_id == comp_id), None)
            pct = matched_sc.percentile if matched_sc else None
            pts = matched_sc.points if matched_sc else None

            scv = ScoreComponentValue(
                id=uuid4(),
                run_id=run_id,
                security_id=cv.security_id,
                component_id=comp_id,
                raw_value=Decimal(str(cv.raw_value)) if cv.raw_value is not None else None,
                percentile_rank=Decimal(str(pct)) if pct is not None else None,
                points=Decimal(str(pts)) if pts is not None else None,
                status=cv.status,
                data_as_of=cv.data_as_of,
                data_age_days=cv.data_age_days,
                evidence_ref=cv.evidence_ref,
            )
            session.add(scv)

    # Persist ConfidenceFactorValue rows
    for sec_id, conf_obj in confidence_results.items():
        for f_name, factor in conf_obj.factors.items():
            cap_note = next(
                (c for c in conf_obj.caps_applied if f_name in c or "cap" in c),
                None,
            )
            cfv = ConfidenceFactorValue(
                id=uuid4(),
                run_id=run_id,
                security_id=sec_id,
                factor_name=f_name,
                factor_value=Decimal(str(factor.factor_value)),
                weight=Decimal(str(factor.weight)),
                cap_applied=cap_note,
            )
            session.add(cfv)

    # Persist AuditLog entry
    audit = AuditLog(
        id=uuid4(),
        timestamp=datetime.now(UTC),
        subject=f"score_run:{run_id}",
        event_type="stock_scores_computed",
        run_id=run_id,
        reason=(
            f"Computed multi-dimensional risk scores for {len(risk_scores)} "
            f"securities as of {as_of.isoformat()}."
        ),
        inputs_ref={
            "as_of": as_of.isoformat(),
            "config_version": config_version,
            "config_fingerprint": config_fingerprint,
            "input_fingerprint": input_fingerprint,
            "active_components": list(active_defs.keys()),
        },
    )
    session.add(audit)
    session.commit()

    return CalculationSummary(
        run_id=run_id,
        is_new=True,
        as_of_date=as_of,
        total_securities=len(universe),
        scored_securities=len(risk_scores),
        config_version=config_version,
        config_fingerprint=config_fingerprint,
        input_fingerprint=input_fingerprint,
    )


def get_latest_stock_scores(
    session: Session,
    industry: str | None = None,
    sort_by: str = "risk",  # risk | confidence | symbol
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Retrieve latest screener view of stock risk scores with pagination."""
    # Find latest completed score run
    latest_run = session.scalars(
        select(ScoreRun)
        .where(ScoreRun.status == "completed")
        .order_by(desc(ScoreRun.as_of_date), desc(ScoreRun.completed_at))
        .limit(1)
    ).first()

    if latest_run is None:
        return {
            "run_id": None,
            "as_of_date": None,
            "total_items": 0,
            "page": page,
            "page_size": page_size,
            "items": [],
        }

    # Query results joined with Security to get industry and company name
    query = (
        select(StockRiskResult, Security.industry, Security.company_name)
        .join(Security, StockRiskResult.security_id == Security.id)
        .where(StockRiskResult.run_id == latest_run.id)
    )

    if industry and industry.lower() != "all":
        query = query.where(Security.industry.ilike(f"%{industry}%"))

    # Sorting
    col: Any
    if sort_by == "risk":
        col = StockRiskResult.total_score
    elif sort_by == "confidence":
        col = StockRiskResult.confidence
    elif sort_by == "coverage":
        col = StockRiskResult.data_coverage
    else:
        col = StockRiskResult.symbol

    order_expr = desc(col) if sort_order.lower() == "desc" else col
    query = query.order_by(order_expr)

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total_items = session.scalar(count_query) or 0

    # Pagination
    offset = max(0, (page - 1) * page_size)
    paginated_query = query.offset(offset).limit(page_size)
    rows = session.execute(paginated_query).all()

    items: list[dict[str, Any]] = []
    for r, ind, comp_name in rows:
        top_reason = r.top_reasons[0] if r.top_reasons else None
        items.append(
            {
                "security_id": str(r.security_id),
                "symbol": r.symbol,
                "company_name": comp_name or r.symbol,
                "industry": ind or "Unknown",
                "total_score": float(r.total_score),
                "confidence": float(r.confidence),
                "data_coverage": float(r.data_coverage),
                "dimension_scores": r.dimension_scores,
                "top_reason": top_reason,
                "limitations": r.limitations,
                "computed_at": r.computed_at.isoformat(),
            }
        )

    return {
        "run_id": str(latest_run.id),
        "as_of_date": latest_run.as_of_date.isoformat(),
        "config_version": latest_run.config_version,
        "total_items": total_items,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def get_stock_risk_envelope(
    session: Session,
    symbol: str,
) -> dict[str, Any] | None:
    """Retrieve full D3 Result Envelope for a specific stock with generic components array."""
    result_row = session.scalars(
        select(StockRiskResult)
        .where(StockRiskResult.symbol == symbol.upper())
        .order_by(desc(StockRiskResult.computed_at))
        .limit(1)
    ).first()

    if result_row is None:
        return None

    sec = session.get(Security, result_row.security_id)
    score_run = session.get(ScoreRun, result_row.run_id)
    if score_run is None:
        return None

    # Retrieve all component definitions (for names, directions, dimensions)
    definitions = {
        d.component_id: d for d in session.scalars(select(ScoreComponentDefinition)).all()
    }

    # Retrieve all component values for this run and security
    comp_values = session.scalars(
        select(ScoreComponentValue).where(
            ScoreComponentValue.run_id == score_run.id,
            ScoreComponentValue.security_id == result_row.security_id,
        )
    ).all()

    # Build generic components array (D2, D5)
    # Even if component is not computed or missing, include it generically
    components_array: list[dict[str, Any]] = []
    comp_val_map = {cv.component_id: cv for cv in comp_values}

    for comp_id, comp_def in definitions.items():
        if not comp_def.active:
            components_array.append(
                {
                    "component_id": comp_id,
                    "name": comp_def.name,
                    "dimension": comp_def.dimension,
                    "direction": comp_def.direction,
                    "raw_value": None,
                    "percentile_rank": None,
                    "points": None,
                    "status": "inactive",
                    "status_label": "Not yet available",
                    "data_as_of": None,
                    "data_age_days": None,
                    "evidence_ref": {},
                }
            )
            continue

        cv = comp_val_map.get(comp_id)
        if cv is None or cv.status == "missing":
            components_array.append(
                {
                    "component_id": comp_id,
                    "name": comp_def.name,
                    "dimension": comp_def.dimension,
                    "direction": comp_def.direction,
                    "raw_value": None,
                    "percentile_rank": None,
                    "points": None,
                    "status": "missing",
                    "status_label": "Not yet available",
                    "data_as_of": None,
                    "data_age_days": None,
                    "evidence_ref": {},
                }
            )
        else:
            components_array.append(
                {
                    "component_id": comp_id,
                    "name": comp_def.name,
                    "dimension": comp_def.dimension,
                    "direction": comp_def.direction,
                    "raw_value": float(cv.raw_value) if cv.raw_value is not None else None,
                    "percentile_rank": (
                        float(cv.percentile_rank) if cv.percentile_rank is not None else None
                    ),
                    "points": float(cv.points) if cv.points is not None else None,
                    "status": cv.status,
                    "status_label": cv.status.capitalize(),
                    "data_as_of": cv.data_as_of.isoformat() if cv.data_as_of else None,
                    "data_age_days": cv.data_age_days,
                    "evidence_ref": cv.evidence_ref,
                }
            )

    # Retrieve confidence factors
    cf_rows = session.scalars(
        select(ConfidenceFactorValue).where(
            ConfidenceFactorValue.run_id == score_run.id,
            ConfidenceFactorValue.security_id == result_row.security_id,
        )
    ).all()
    factors_dict = {
        cf.factor_name: {
            "value": float(cf.factor_value),
            "weight": float(cf.weight),
            "cap_applied": cf.cap_applied,
        }
        for cf in cf_rows
    }

    comp_name = (sec.company_name if sec else None) or result_row.symbol
    ind_name = (sec.industry if sec else None) or "General"

    # Construct D3 Result Envelope
    envelope: dict[str, Any] = {
        "subject": f"stock:{result_row.symbol}",
        "symbol": result_row.symbol,
        "company_name": comp_name,
        "industry": ind_name,
        "effective_time": score_run.as_of_date.isoformat(),
        "method": "prism_multidimensional_risk_synthesis",
        "version": score_run.config_version,
        "method_version": f"risk-scorer-{score_run.config_version}",
        "input_fingerprint": score_run.input_fingerprint,
        "config_fingerprint": score_run.config_fingerprint,
        "units": "points_0_to_100",
        "total_score": float(result_row.total_score),
        "confidence": {
            "score": float(result_row.confidence),
            "factors": factors_dict,
        },
        "data_sufficiency": (
            "sufficient" if float(result_row.data_coverage) >= 0.70 else "partial"
        ),
        "data_coverage": float(result_row.data_coverage),
        "dimension_scores": result_row.dimension_scores,
        "component_contributions": result_row.top_reasons,
        "components": components_array,
        "thresholds": {
            "min_coverage_ratio": 0.70,
            "stale_price_days": 5,
        },
        "limitations": result_row.limitations
        + [
            (
                "PRISM provides descriptive risk and explanation, "
                "NOT price prediction and NOT investment advice."
            )
        ],
        "computed_at": result_row.computed_at.isoformat(),
    }

    return envelope


def get_stock_risk_history(
    session: Session,
    symbol: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Retrieve time-series risk score trajectory for a stock."""
    rows = session.execute(
        select(StockRiskResult, ScoreRun.as_of_date)
        .join(ScoreRun, StockRiskResult.run_id == ScoreRun.id)
        .where(StockRiskResult.symbol == symbol.upper())
        .order_by(desc(ScoreRun.as_of_date))
        .limit(limit)
    ).all()

    trajectory: list[dict[str, Any]] = []
    for r, as_of in rows:
        trajectory.append(
            {
                "as_of_date": as_of.isoformat(),
                "total_score": float(r.total_score),
                "confidence": float(r.confidence),
                "data_coverage": float(r.data_coverage),
                "dimension_scores": r.dimension_scores,
            }
        )

    return trajectory
