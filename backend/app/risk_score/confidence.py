"""Point-in-time Confidence score engine and factor synthesis (D1, D3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from backend.app.db.models import DataCrosscheck, MstStability
from backend.app.risk_score.components.base import RiskContext
from backend.app.risk_score.scorer import SecurityRiskScore


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
        crosscheck_rows = session.scalars(
            select(DataCrosscheck).where(
                DataCrosscheck.security_id.in_(sec_ids),
                DataCrosscheck.trade_date <= as_of,
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
            float(mst_stability_row.edge_persistence)
            if mst_stability_row is not None
            else 0.90
        )

        results: dict[UUID, SecurityConfidenceResult] = {}

        for sec_id, score_obj in risk_scores.items():
            caps_applied: list[str] = []
            factors: dict[str, ConfidenceFactor] = {}

            # --- Factor 1: Data Coverage ---
            f_cov = min(1.0, max(0.0, score_obj.coverage))
            factors["data_coverage"] = ConfidenceFactor(
                factor_name="data_coverage",
                factor_value=round(f_cov, 4),
                weight=self.factor_weights.get("data_coverage", 1.0),
                description="Share of available risk dimension weights",
                details={"coverage_ratio": score_obj.coverage},
            )

            # --- Factor 2: Data Freshness ---
            valid_comps = [c for c in score_obj.components if c.points is not None]
            if valid_comps:
                freshness_scores: list[float] = []
                for c in valid_comps:
                    max_age = self.max_age_by_dimension.get(c.dimension, 5)
                    age = c.data_age_days if c.data_age_days is not None else 0
                    comp_f = max(0.0, 1.0 - (age / max_age))
                    freshness_scores.append(comp_f)
                f_fresh = float(sum(freshness_scores) / len(freshness_scores))
            else:
                f_fresh = 0.5
            factors["data_freshness"] = ConfidenceFactor(
                factor_name="data_freshness",
                factor_value=round(f_fresh, 4),
                weight=self.factor_weights.get("data_freshness", 1.0),
                description="Linear calendar freshness of underlying inputs",
                details={"evaluated_components": len(valid_comps)},
            )

            # --- Factor 3: Source Agreement ---
            cc_list = crosscheck_by_sec.get(sec_id, [])
            if cc_list:
                max_diff = max(float(cc.rel_diff) for cc in cc_list)
                f_source = max(0.0, 1.0 - min(1.0, max_diff * 10.0))
            else:
                f_source = 1.0  # Official primary source verified
            factors["source_agreement"] = ConfidenceFactor(
                factor_name="source_agreement",
                factor_value=round(f_source, 4),
                weight=self.factor_weights.get("source_agreement", 1.0),
                description="Concordance across redundant price sources",
                details={"crosschecks_count": len(cc_list)},
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
                description="Share of risk components pointing to the same side of median",
                details={"components_evaluated": len(valid_comps)},
            )

            # --- Factor 5: Model Stability ---
            # Combine MST edge persistence and component status completeness
            f_stability = min(1.0, max(0.0, base_mst_persistence))
            factors["model_stability"] = ConfidenceFactor(
                factor_name="model_stability",
                factor_value=round(f_stability, 4),
                weight=self.factor_weights.get("model_stability", 1.0),
                description="Structural robustness and edge persistence of underlying models",
                details={"base_mst_persistence": base_mst_persistence},
            )

            # --- Factor 6: Evidence Volume ---
            # Proportion of active components that met sample size requirements
            active_defs_count = sum(1 for c in score_obj.components)
            if active_defs_count > 0:
                f_volume = min(1.0, len(valid_comps) / active_defs_count)
            else:
                f_volume = 1.0
            factors["evidence_volume"] = ConfidenceFactor(
                factor_name="evidence_volume",
                factor_value=round(f_volume, 4),
                weight=self.factor_weights.get("evidence_volume", 1.0),
                description="Degree to which statistical sample size is satisfied",
                details={"valid_components": len(valid_comps), "total": active_defs_count},
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
                (c.data_age_days or 0) > self.stale_price_limit for c in market_comps
            )
            if has_stale_market_price:
                if final_c > self.stale_price_cap:
                    final_c = self.stale_price_cap
                    caps_applied.append(f"stale_price_cap_{int(self.stale_price_cap)}")

            # Check 2: Low coverage cap (coverage < min_coverage_ratio)
            if score_obj.coverage < self.min_coverage_ratio:
                if final_c > self.low_coverage_cap:
                    final_c = self.low_coverage_cap
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
