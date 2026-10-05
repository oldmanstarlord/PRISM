"""Dynamic multi-dimensional risk score synthesizer (D1, D2, D3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import numpy as np

from backend.app.risk_score.components.base import ComponentValue
from backend.app.risk_score.registry import RegisteredComponentDefinition


@dataclass
class ScoredComponent:
    """Evaluated component score for a security."""

    component_id: str
    dimension: str
    name: str
    raw_value: float | None
    percentile: float | None
    direction: str
    points: float | None
    status: str
    data_as_of: date | None
    data_age_days: int | None
    weight: float
    contribution: float  # Points contributed to final overall score
    scope_used: str  # universe | industry
    evidence_ref: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


@dataclass
class ScoredDimension:
    """Aggregated score for a single risk dimension."""

    dimension: str
    score: float | None
    weight: float
    status: str  # ok | missing | partial
    components: list[ScoredComponent] = field(default_factory=list)


@dataclass
class SecurityRiskScore:
    """Full synthesized risk score for a single security."""

    security_id: UUID
    symbol: str
    industry: str
    overall_score: float
    coverage: float
    status: str  # ok | partial | insufficient
    dimensions: dict[str, ScoredDimension]
    components: list[ScoredComponent]
    top_reasons: list[dict[str, Any]]
    limitations: list[str]


def compute_weak_percentile(value: float, peer_values: list[float]) -> float:
    """Calculate weak empirical percentile rank with midpoint adjustment.

    percentile(v) = 100 * (count(x < v) + 0.5 * count(x == v)) / N
    """
    arr = np.array(peer_values, dtype=float)
    n = len(arr)
    if n == 0:
        return 50.0
    less = np.sum(arr < value)
    equal = np.sum(arr == value)
    return float(100.0 * (less + 0.5 * equal) / n)


class RiskScorer:
    """Config-driven risk score synthesis engine."""

    def __init__(
        self,
        config: dict[str, Any],
        definitions: dict[str, RegisteredComponentDefinition],
    ) -> None:
        self.config = config
        self.definitions = definitions
        self.dim_weights: dict[str, float] = self.config.get(
            "dimension_weights",
            {
                "market": 25.0,
                "fundamentals": 20.0,
                "liquidity": 10.0,
                "structure": 10.0,
                "relative": 10.0,
                "governance": 10.0,
                "events": 10.0,
                "macro": 5.0,
            },
        )
        self.min_coverage_ratio = float(self.config.get("min_coverage_ratio", 0.70))
        self.min_industry_size = int(self.config.get("min_industry_group_size", 5))
        self.reason_templates = self.config.get(
            "reason_templates",
            {
                "higher_is_riskier": (
                    "{component_name} is elevated at the {percentile:.0f}th percentile "
                    "({raw_value:.2f}), contributing +{contribution:.1f} pts to {dimension} risk."
                ),
                "lower_is_riskier": (
                    "{component_name} is depressed at the {percentile:.0f}th percentile "
                    "({raw_value:.2f}), adding +{contribution:.1f} pts to {dimension} risk."
                ),
            },
        )

    def synthesize(
        self,
        universe: list[tuple[UUID, str, str]],  # (sec_id, symbol, industry)
        component_values_by_key: dict[str, list[ComponentValue]],
    ) -> dict[UUID, SecurityRiskScore]:
        """Synthesize overall risk scores for all universe securities."""
        # 1. Map values by (component_key, sec_id)
        val_map: dict[str, dict[UUID, ComponentValue]] = {}
        for key, vals in component_values_by_key.items():
            val_map[key] = {v.security_id: v for v in vals}

        # 2. Industry grouping
        industry_map: dict[UUID, str] = {sec_id: ind for sec_id, _, ind in universe}
        sec_ids_by_industry: dict[str, list[UUID]] = {}
        for sec_id, _, ind in universe:
            sec_ids_by_industry.setdefault(ind, []).append(sec_id)

        # 3. Compute percentile ranks for each component
        # Map: sec_id -> list of ScoredComponent (un-weighted contribution yet)
        sec_components: dict[UUID, list[ScoredComponent]] = {
            sec_id: [] for sec_id, _, _ in universe
        }

        for comp_key, comp_def in self.definitions.items():
            if not comp_def.active:
                continue

            vals_for_comp = val_map.get(comp_key, {})
            # Separate valid non-null values
            valid_universe_values: list[float] = [
                cv.raw_value
                for cv in vals_for_comp.values()
                if cv.raw_value is not None
            ]

            # Industry-specific lists of valid values
            industry_values: dict[str, list[float]] = {}
            for s_id, comp_val in vals_for_comp.items():
                if comp_val.raw_value is not None:
                    ind = industry_map.get(s_id, "Unknown")
                    industry_values.setdefault(ind, []).append(comp_val.raw_value)

            for sec_id, _symbol, industry in universe:
                cv = vals_for_comp.get(sec_id)
                if cv is None or cv.raw_value is None:
                    # Missing component observation
                    status = cv.status if cv else "missing"
                    age = cv.data_age_days if cv else None
                    as_of_dt = cv.data_as_of if cv else None
                    ev_ref = cv.evidence_ref if cv else {}
                    sec_components[sec_id].append(
                        ScoredComponent(
                            component_id=comp_key,
                            dimension=comp_def.dimension,
                            name=comp_def.name,
                            raw_value=None,
                            percentile=None,
                            direction=comp_def.direction,
                            points=None,
                            status=status,
                            data_as_of=as_of_dt,
                            data_age_days=age,
                            weight=comp_def.weight,
                            contribution=0.0,
                            scope_used=comp_def.scope,
                            evidence_ref=ev_ref,
                            limitations=[f"missing_{comp_key}"],
                        )
                    )
                    continue

                raw_val = cv.raw_value
                scope_used = comp_def.scope
                limitations: list[str] = []

                if cv.status == "stale":
                    limitations.append(f"stale_data_{comp_key}")

                # Determine peer group values
                if comp_def.scope == "industry":
                    ind_vals = industry_values.get(industry, [])
                    if len(ind_vals) < comp_def.min_group_size:
                        peer_vals = valid_universe_values
                        scope_used = "universe"
                        limitations.append("industry_group_undersized_fallback")
                    else:
                        peer_vals = ind_vals
                else:
                    peer_vals = valid_universe_values

                raw_pct = compute_weak_percentile(raw_val, peer_vals)

                # Direction handling
                if comp_def.direction == "lower_is_riskier":
                    points = 100.0 - raw_pct
                else:
                    points = raw_pct

                sec_components[sec_id].append(
                    ScoredComponent(
                        component_id=comp_key,
                        dimension=comp_def.dimension,
                        name=comp_def.name,
                        raw_value=raw_val,
                        percentile=round(raw_pct, 4),
                        direction=comp_def.direction,
                        points=round(points, 4),
                        status=cv.status,
                        data_as_of=cv.data_as_of,
                        data_age_days=cv.data_age_days,
                        weight=comp_def.weight,
                        contribution=0.0,  # Will compute after dimension weighting
                        scope_used=scope_used,
                        evidence_ref=cv.evidence_ref,
                        limitations=limitations,
                    )
                )

        # 4. Dimension aggregation, missing-component renormalisation, contributions
        results: dict[UUID, SecurityRiskScore] = {}
        total_possible_weight = sum(self.dim_weights.values())

        for sec_id, symbol, industry in universe:
            comps = sec_components[sec_id]
            dim_groups: dict[str, list[ScoredComponent]] = {}
            for c in comps:
                dim_groups.setdefault(c.dimension, []).append(c)

            dim_scores: dict[str, ScoredDimension] = {}
            avail_dim_weights: float = 0.0
            weighted_points_sum: float = 0.0
            all_limitations: list[str] = []

            for dim, d_weight in self.dim_weights.items():
                c_list = dim_groups.get(dim, [])
                valid_c = [c for c in c_list if c.points is not None]

                if not valid_c:
                    dim_scores[dim] = ScoredDimension(
                        dimension=dim,
                        score=None,
                        weight=d_weight,
                        status="missing",
                        components=c_list,
                    )
                    all_limitations.append(f"dimension_{dim}_missing")
                    continue

                # Dimension score = weighted average of component points
                sum_w = sum(c.weight for c in valid_c)
                dim_score = sum(c.weight * (c.points or 0.0) for c in valid_c) / sum_w
                status = "ok" if len(valid_c) == len(c_list) else "partial"

                dim_scores[dim] = ScoredDimension(
                    dimension=dim,
                    score=round(dim_score, 4),
                    weight=d_weight,
                    status=status,
                    components=c_list,
                )
                avail_dim_weights += d_weight
                weighted_points_sum += d_weight * dim_score

            # Coverage
            coverage = (
                avail_dim_weights / total_possible_weight
                if total_possible_weight > 0
                else 0.0
            )

            # Renormalised overall score
            if avail_dim_weights > 0:
                overall_score = weighted_points_sum / avail_dim_weights
            else:
                overall_score = 50.0  # Fallback median

            # Determine security status
            if coverage < self.min_coverage_ratio:
                sec_status = "insufficient"
                all_limitations.append(
                    f"low_data_coverage_{round(coverage * 100, 1)}%"
                )
            elif any(d.status != "ok" for d in dim_scores.values()):
                sec_status = "partial"
            else:
                sec_status = "ok"

            # Compute component contributions to overall score:
            # contribution_c = (W_d / W_avail) * (w_c / sum_w_in_d) * p_c
            for _dim, d_obj in dim_scores.items():
                if d_obj.score is None:
                    continue
                d_weight = d_obj.weight
                valid_c = [c for c in d_obj.components if c.points is not None]
                sum_w_in_d = sum(c.weight for c in valid_c)
                dim_weight_frac = (
                    d_weight / avail_dim_weights if avail_dim_weights > 0 else 0.0
                )

                for c in valid_c:
                    comp_weight_frac = c.weight / sum_w_in_d if sum_w_in_d > 0 else 0.0
                    points_val = c.points if c.points is not None else 0.0
                    c.contribution = round(
                        dim_weight_frac * comp_weight_frac * points_val, 4
                    )
                    all_limitations.extend(c.limitations)

            # Top 3 reasons
            valid_comps_for_reasons = [c for c in comps if c.points is not None]
            valid_comps_for_reasons.sort(key=lambda x: x.contribution, reverse=True)
            top_3 = valid_comps_for_reasons[:3]

            top_reasons: list[dict[str, Any]] = []
            for c in top_3:
                template = self.reason_templates.get(
                    c.direction,
                    "{component_name} contributes +{contribution:.1f} pts to {dimension} risk.",
                )
                formatted_text = template.format(
                    component_name=c.name,
                    percentile=c.percentile if c.percentile is not None else 50.0,
                    raw_value=c.raw_value if c.raw_value is not None else 0.0,
                    contribution=c.contribution,
                    dimension=c.dimension.capitalize(),
                )
                top_reasons.append(
                    {
                        "component_id": c.component_id,
                        "dimension": c.dimension,
                        "name": c.name,
                        "contribution": round(c.contribution, 2),
                        "percentile": c.percentile,
                        "raw_value": c.raw_value,
                        "direction": c.direction,
                        "text": formatted_text,
                    }
                )

            # Deduplicate limitations while preserving order
            unique_limits: list[str] = list(dict.fromkeys(all_limitations))

            results[sec_id] = SecurityRiskScore(
                security_id=sec_id,
                symbol=symbol,
                industry=industry,
                overall_score=round(overall_score, 2),
                coverage=round(coverage, 4),
                status=sec_status,
                dimensions=dim_scores,
                components=comps,
                top_reasons=top_reasons,
                limitations=unique_limits,
            )

        return results
