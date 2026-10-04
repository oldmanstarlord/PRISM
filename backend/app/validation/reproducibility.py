"""Stable semantic digests for deterministic quantitative outputs."""

import hashlib
import json

from backend.app.correlation_mst.calculator import MstCalculation
from backend.app.sector_divergence.calculator import SectorDivergenceCalculation


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def sector_divergence_digest(calculation: SectorDivergenceCalculation) -> str:
    return _digest(
        {
            "signal_date": calculation.signal_date,
            "implementation_version": calculation.implementation_version,
            "scores": [
                {
                    "security_id": score.security_id,
                    "symbol": score.symbol,
                    "industry": score.industry,
                    "horizon": score.horizon,
                    "residual_value": score.residual_value,
                    "divergence_value": score.divergence_value,
                    "alpha": score.alpha,
                    "beta": score.beta,
                    "residual_volatility": score.residual_volatility,
                    "industry_percentile": score.industry_percentile,
                    "interpretation": score.interpretation,
                    "lookback_start": score.lookback_start,
                    "lookback_end": score.lookback_end,
                    "observations_used": score.observations_used,
                    "data_cutoff": score.data_cutoff,
                    "membership_source": score.membership_source,
                    "adjustment_version": score.adjustment_version,
                }
                for score in calculation.scores
            ],
            "issues": [
                [issue.security_id, issue.symbol, issue.signal_date, issue.horizon,
                 issue.reason, issue.details]
                for issue in calculation.issues
            ],
            "exclusions": [
                [item.security_id, item.symbol, item.reason, item.details]
                for item in calculation.input_exclusions
            ],
        }
    )


def mst_digest(calculation: MstCalculation) -> str:
    return _digest(
        {
            "window_start": calculation.window_start,
            "window_end": calculation.window_end,
            "implementation_version": calculation.implementation_version,
            "nodes": [
                [node.security_id, node.symbol, node.industry, node.observations_used,
                 node.membership_source]
                for node in calculation.nodes
            ],
            "edges": [
                [edge.security_a_id, edge.security_b_id, edge.symbol_a, edge.symbol_b,
                 edge.correlation, edge.distance, edge.paired_observations, edge.edge_rank]
                for edge in calculation.edges
            ],
            "exclusions": [
                [item.security_id, item.symbol, item.reason, item.details]
                for item in calculation.exclusions
            ],
            "is_connected": calculation.is_connected,
            "is_acyclic": calculation.is_acyclic,
        }
    )
