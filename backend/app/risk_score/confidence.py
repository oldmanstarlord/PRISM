"""Point-in-time Confidence score engine and factor synthesis (D1, D3)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from backend.app.db.models import DataCrosscheck, MstStability
from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.scorer import SecurityRiskScore

FACTOR_DESCRIPTIONS: dict[str, str] = {
    "data_coverage": "Configured dimension weight supported by usable real observations.",
    "data_freshness": "Component-weighted age against each dimension's maximum age.",
    "source_agreement": "Observed agreement rate across available independent cross-checks.",
    "signal_agreement": "Share of usable component signals on the dominant side of median risk.",
    "model_stability": "Observed MST persistence and volatility-estimation reliability.",
    "evidence_volume": "Saturating event and matched-policy evidence count.",
}


@dataclass
class ConfidenceFactor:
    """Individual factor contributing to confidence synthesis."""

    factor_name: str
    factor_value: float  # Range [0.0, 1.0]
    weight: float
    description: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfidenceResult:
    """Confidence evaluation result for a security."""

    security_id: UUID
    symbol: str
    raw_confidence: float
    final_confidence: float
    factors: dict[str, ConfidenceFactor]
    caps_applied: list[str]


class ConfidenceEngine:
    """Config-driven Confidence v1 engine."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.min_coverage_ratio = float(self.config.get("min_coverage_ratio", 0.70))
        self.stale_price_limit = int(self.config.get("stale_price_days_cap_threshold", 5))
        self.low_coverage_cap = float(self.config.get("low_coverage_cap", 60.0))
        self.stale_price_cap = float(self.config.get("stale_price_cap", 50.0))
        self.factor_weights: dict[str, float] = self.config.get(
            "confidence_factor_weights",
            {
                "data_coverage": 1.0,
                "data_freshness": 1.0,
                "source_agreement": 1.0,
                "signal_agreement": 1.0,
                "model_stability": 1.0,
                "evidence_volume": 1.0,
            },
        )
        self.max_age_by_dimension: dict[str, int] = self.config.get(
            "confidence_max_age_days",
            {
                "market": 5,
                "liquidity": 5,
                "structure": 35,
                "relative": 5,
                "fundamentals": 120,
                "governance": 365,
                "events": 30,
                "macro": 30,
            },
        )

    def evaluate(
        self,
        risk_scores: dict[UUID, SecurityRiskScore],
        context: RiskContext,
    ) -> dict[UUID, SecurityConfidenceResult]:
        """Evaluate confidence for all securities in the scored universe."""
        session = context.session
        as_of = context.as_of

        # 1. Preload recent data crosschecks for universe point-in-time
        sec_ids = list(risk_scores.keys())
        source_lookback = int(self.config.get("source_agreement_lookback_days", 60))
        crosscheck_rows = session.scalars(
            select(DataCrosscheck).where(
                DataCrosscheck.security_id.in_(sec_ids),
                DataCrosscheck.trade_date <= as_of,
                DataCrosscheck.trade_date >= as_of - timedelta(days=source_lookback),
                DataCrosscheck.checked_at <= context.data_cutoff,
            )
        ).all()
        crosscheck_by_sec: dict[UUID, list[DataCrosscheck]] = {}
        for row in crosscheck_rows:
            crosscheck_by_sec.setdefault(row.security_id, []).append(row)

        # 2. Preload latest MST stability point-in-time if available
        mst_stability_row = session.scalars(
            select(MstStability)
            .where(MstStability.created_at <= context.data_cutoff)
            .order_by(desc(MstStability.created_at))
            .limit(1)
        ).first()
        base_mst_persistence = (
            float(mst_stability_row.edge_persistence) if mst_stability_row is not None else None
        )

        results: dict[UUID, SecurityConfidenceResult] = {}

        for sec_id, score_obj in risk_scores.items():
            caps_applied: list[str] = []
            factors: dict[str, ConfidenceFactor] = {}

            # --- Factor 1: Data Coverage ---
            dimension_coverage = min(1.0, max(0.0, score_obj.coverage))
            history_ratios: list[float] = []
            missing_history_days = 0
            required_by_component = self.config.get("coverage_required_observations", {})
            if not isinstance(required_by_component, dict):
                required_by_component = {}
            for component in score_obj.components:
                observations = component.evidence_ref.get(
                    "observations", component.evidence_ref.get("paired_observations")
                )
                required = component.evidence_ref.get(
                    "required", required_by_component.get(component.component_id)
                )
                if isinstance(observations, (int, float)) and isinstance(required, (int, float)):
                    if required > 0:
                        history_ratios.append(min(1.0, max(0.0, observations / required)))
                        missing_history_days += max(0, int(required - observations))
            history_completeness = (
                sum(history_ratios) / len(history_ratios) if history_ratios else 1.0
            )
            f_cov = dimension_coverage * history_completeness
            factors["data_coverage"] = ConfidenceFactor(
                factor_name="data_coverage",
                factor_value=round(f_cov, 4),
                weight=self.factor_weights.get("data_coverage", 1.0),
                description=FACTOR_DESCRIPTIONS["data_coverage"],
                details={
                    "dimension_weight_coverage": dimension_coverage,
                    "history_completeness": round(history_completeness, 4),
                    "missing_history_days": missing_history_days,
                    "missing_components": sum(
                        component.points is None for component in score_obj.components
                    ),
                },
            )

            # --- Factor 2: Data Freshness ---
            valid_comps = [c for c in score_obj.components if c.points is not None]
            if valid_comps:
                weighted_freshness = 0.0
                freshness_weight = 0.0
                for c in valid_comps:
                    max_age = self.max_age_by_dimension.get(c.dimension, 5)
                    age = c.data_age_days
                    comp_f = max(0.0, 1.0 - (age / max_age)) if age is not None else 0.0
                    if c.dimension == "fundamentals":
                        is_est = c.evidence_ref.get(
                            "published_at_method"
                        ) == "estimated" or "estimated" in str(c.evidence_ref)
                        if is_est:
                            comp_f *= 0.85
                    weighted_freshness += c.weight * comp_f
                    freshness_weight += c.weight
                f_fresh = weighted_freshness / freshness_weight if freshness_weight > 0 else 0.0
            else:
                f_fresh = 0.0
            factors["data_freshness"] = ConfidenceFactor(
                factor_name="data_freshness",
                factor_value=round(f_fresh, 4),
                weight=self.factor_weights.get("data_freshness", 1.0),
                description=FACTOR_DESCRIPTIONS["data_freshness"],
                details={
                    "evaluated_components": len(valid_comps),
                    "weighted_by_component_weight": True,
                },
            )

            # --- Factor 3: Source Agreement ---
            cc_list = crosscheck_by_sec.get(sec_id, [])
            if cc_list:
                mismatch_count = sum(cc.status != "match" for cc in cc_list)
                mismatch_rate = mismatch_count / len(cc_list)
                f_source = max(0.0, 1.0 - mismatch_rate)
            else:
                mismatch_count = 0
                mismatch_rate = None
                f_source = 0.0
            factors["source_agreement"] = ConfidenceFactor(
                factor_name="source_agreement",
                factor_value=round(f_source, 4),
                weight=self.factor_weights.get("source_agreement", 1.0),
                description=FACTOR_DESCRIPTIONS["source_agreement"],
                details={
                    "crosschecks_count": len(cc_list),
                    "mismatch_count": mismatch_count,
                    "mismatch_rate": mismatch_rate,
                    "status": "missing" if not cc_list else "ok",
                },
            )

            # --- Factor 4: Signal Agreement ---
            # Share of components pointing the same side of the median (50th percentile)
            if valid_comps:
                above_med = sum(1 for c in valid_comps if (c.points or 50.0) >= 50.0)
                below_med = len(valid_comps) - above_med
                f_signal = max(above_med, below_med) / len(valid_comps)
            else:
                f_signal = 0.5
            factors["signal_agreement"] = ConfidenceFactor(
                factor_name="signal_agreement",
                factor_value=round(f_signal, 4),
                weight=self.factor_weights.get("signal_agreement", 1.0),
                description=FACTOR_DESCRIPTIONS["signal_agreement"],
                details={"components_evaluated": len(valid_comps)},
            )

            # --- Factor 5: Model Stability ---
            # Combine observed MST persistence and volatility estimation reliability.
            stability_inputs: list[float] = []
            if base_mst_persistence is not None:
                stability_inputs.append(min(1.0, max(0.0, base_mst_persistence)))
            volatility_observations: list[int] = []
            for component in valid_comps:
                if component.component_id != "ewma_volatility":
                    continue
                observations = component.evidence_ref.get("observations")
                if isinstance(observations, int) and observations > 1:
                    volatility_observations.append(observations)
                    relative_error = math.sqrt(1.0 / (2.0 * (observations - 1)))
                    stability_inputs.append(max(0.0, 1.0 - relative_error))
            f_stability = (
                sum(stability_inputs) / len(stability_inputs) if stability_inputs else 0.0
            )
            factors["model_stability"] = ConfidenceFactor(
                factor_name="model_stability",
                factor_value=round(f_stability, 4),
                weight=self.factor_weights.get("model_stability", 1.0),
                description=FACTOR_DESCRIPTIONS["model_stability"],
                details={
                    "mst_edge_persistence": base_mst_persistence,
                    "volatility_observations": volatility_observations,
                    "status": "missing" if not stability_inputs else "ok",
                },
            )

            # --- Factor 6: Evidence Volume ---
            event_count = 0
            matched_policy_count = 0
            for component in score_obj.components:
                raw_event_count = component.evidence_ref.get("event_count", 0)
                raw_policy_count = component.evidence_ref.get("matched_policy_count", 0)
                if isinstance(raw_event_count, int):
                    event_count += raw_event_count
                if isinstance(raw_policy_count, int):
                    matched_policy_count += raw_policy_count
            evidence_count = event_count + matched_policy_count
            scale = max(0.0001, float(self.config.get("evidence_volume_scale", 5.0)))
            f_volume = 1.0 - math.exp(-evidence_count / scale)
            factors["evidence_volume"] = ConfidenceFactor(
                factor_name="evidence_volume",
                factor_value=round(f_volume, 4),
                weight=self.factor_weights.get("evidence_volume", 1.0),
                description=FACTOR_DESCRIPTIONS["evidence_volume"],
                details={
                    "event_count": event_count,
                    "matched_policy_count": matched_policy_count,
                    "saturation_scale": scale,
                },
            )

            # Calculate unconstrained raw confidence
            total_w = sum(f.weight for f in factors.values())
            raw_c = (
                100.0 * sum(f.weight * f.factor_value for f in factors.values()) / total_w
                if total_w > 0
                else 50.0
            )

            # Apply hard caps (from CONFIDENCE_SPEC.md)
            final_c = raw_c

            # Check 1: Stale price data cap (market components older than stale_price_limit)
            market_comps = [c for c in valid_comps if c.dimension == "market"]
            has_stale_market_price = any(
                c.status == "stale"
                or (c.data_age_days is not None and c.data_age_days > self.stale_price_limit)
                for c in market_comps
            )
            if has_stale_market_price:
                final_c = min(final_c, self.stale_price_cap)
                caps_applied.append(f"stale_price_cap_{int(self.stale_price_cap)}")

            # Check 2: Low coverage cap (coverage < min_coverage_ratio)
            if f_cov < self.min_coverage_ratio:
                final_c = min(final_c, self.low_coverage_cap)
                caps_applied.append(f"low_coverage_cap_{int(self.low_coverage_cap)}")

            results[sec_id] = SecurityConfidenceResult(
                security_id=sec_id,
                symbol=score_obj.symbol,
                raw_confidence=round(raw_c, 2),
                final_confidence=round(final_c, 2),
                factors=factors,
                caps_applied=caps_applied,
            )

        return results
