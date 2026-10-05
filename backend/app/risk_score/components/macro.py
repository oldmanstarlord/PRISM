"""Macroeconomic regime & sector sensitivity risk component (dimension: macro)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import desc, select

from backend.app.db.models import (
    MacroObservation,
    MarketRegime,
    SectorMacroSensitivity,
)
from backend.app.risk_score.components.base import ComponentValue, RiskContext


class MacroExposureComponent:
    """Evaluates stock vulnerability to macro shocks transmitted through sector sensitivities."""

    key = "macro_exposure"
    dimension = "macro"
    direction = "higher_is_riskier"
    required_inputs = ["sector_macro_sensitivity", "market_regime", "macro_observation"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],  # (security_id, symbol, industry)
        context: RiskContext,
    ) -> list[ComponentValue]:
        session = context.session
        cutoff = context.data_cutoff or datetime.combine(as_of, datetime.max.time(), tzinfo=UTC)

        # 1. Load latest market regime as of date
        regime_row = session.scalars(
            select(MarketRegime)
            .where(
                MarketRegime.as_of <= as_of,
            )
            .order_by(desc(MarketRegime.as_of))
            .limit(1)
        ).first()

        current_regime = regime_row.regime if regime_row else "calm"
        multipliers = context.config.get(
            "regime_multipliers",
            {
                "calm": 1.0,
                "trending": 1.25,
                "stressed": 1.5,
            },
        )
        regime_multiplier = float(multipliers.get(current_regime, 1.0))

        # 2. Compute recent macro shock z-scores for all active series
        # Window: trailing 5 days vs trailing 63 days baseline
        recent_days = int(context.config.get("recent_move_window_days", 5))
        baseline_days = int(context.config.get("recent_move_baseline_days", 63))
        min_date = as_of - timedelta(days=int(baseline_days * 2.2))

        series_obs_rows = session.execute(
            select(
                MacroObservation.series_key,
                MacroObservation.obs_date,
                MacroObservation.value,
            )
            .where(
                MacroObservation.obs_date <= as_of,
                MacroObservation.obs_date >= min_date,
                MacroObservation.published_at <= cutoff,
            )
            .order_by(MacroObservation.series_key, MacroObservation.obs_date.asc())
        ).all()

        obs_by_series: dict[str, list[tuple[date, float]]] = {}
        for s_key, obs_d, val in series_obs_rows:
            obs_by_series.setdefault(s_key, []).append((obs_d, float(val)))

        z_scores: dict[str, float] = {}
        recent_deltas: dict[str, float] = {}

        for s_key, date_vals in obs_by_series.items():
            if len(date_vals) < 10:
                z_scores[s_key] = 0.0
                recent_deltas[s_key] = 0.0
                continue

            # Compute daily changes
            deltas: list[float] = []
            for i in range(1, len(date_vals)):
                v_cur = date_vals[i][1]
                v_prev = date_vals[i - 1][1]
                if s_key in ("in_10y_yield", "fii_dii_net_flows"):
                    d = v_cur - v_prev
                else:
                    d = (v_cur - v_prev) / v_prev if abs(v_prev) > 1e-8 else 0.0
                deltas.append(d)

            if not deltas:
                z_scores[s_key] = 0.0
                recent_deltas[s_key] = 0.0
                continue

            # Baseline mean and standard deviation over trailing baseline_days
            baseline_deltas = deltas[-baseline_days:] if len(deltas) >= baseline_days else deltas
            mu = float(np.mean(baseline_deltas))
            sigma = float(np.std(baseline_deltas, ddof=1)) if len(baseline_deltas) > 1 else 0.0

            # Cumulative or average move over recent_days window
            recent_slice = deltas[-recent_days:] if len(deltas) >= recent_days else deltas
            recent_move = float(np.sum(recent_slice))
            recent_deltas[s_key] = round(recent_move, 4)

            if sigma > 1e-8:
                z = (recent_move - mu) / sigma
                z_scores[s_key] = float(abs(z))
            else:
                z_scores[s_key] = 0.0

        # 3. Load latest sector sensitivities for all industries
        sens_rows = session.scalars(
            select(SectorMacroSensitivity)
            .where(
                SectorMacroSensitivity.window_end <= as_of,
            )
            .order_by(desc(SectorMacroSensitivity.window_end))
        ).all()

        # Keep latest window_end per (industry, series_key)
        latest_sens: dict[tuple[str, str], SectorMacroSensitivity] = {}
        for s in sens_rows:
            key = (s.industry, s.series_key)
            if key not in latest_sens:
                latest_sens[key] = s

        # 4. Compute macro_exposure for each security
        results: list[ComponentValue] = []
        for sec_id, symbol, industry in universe:
            ind = industry or "General"

            raw_exposure = 0.0
            series_contributions: dict[str, Any] = {}
            has_sensitivities = False

            for s_key in obs_by_series.keys():
                sens_obj = latest_sens.get((ind, s_key))
                z = z_scores.get(s_key, 0.0)

                if sens_obj is not None:
                    has_sensitivities = True
                    beta = sens_obj.beta
                    is_sig = sens_obj.is_significant
                    effective_beta = abs(beta) if is_sig else 0.0
                    contrib = effective_beta * z
                    raw_exposure += contrib

                    series_contributions[s_key] = {
                        "beta": beta,
                        "t_stat": sens_obj.t_stat,
                        "is_significant": is_sig,
                        "z_score": round(z, 2),
                        "recent_move": recent_deltas.get(s_key, 0.0),
                        "contribution": round(contrib, 4),
                    }
                else:
                    series_contributions[s_key] = {
                        "beta": 0.0,
                        "t_stat": 0.0,
                        "is_significant": False,
                        "z_score": round(z, 2),
                        "recent_move": recent_deltas.get(s_key, 0.0),
                        "contribution": 0.0,
                    }

            scaled_exposure = raw_exposure * regime_multiplier

            status = "ok" if has_sensitivities else "missing"
            evidence = {
                "regime": current_regime,
                "regime_multiplier": regime_multiplier,
                "industry": ind,
                "raw_exposure": round(raw_exposure, 4),
                "scaled_exposure": round(scaled_exposure, 4),
                "series_contributions": series_contributions,
            }

            data_as_of = regime_row.as_of if regime_row else as_of
            age_days = (as_of - data_as_of).days if data_as_of else 0

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(scaled_exposure, 4) if status == "ok" else None,
                    status=status,
                    data_as_of=data_as_of,
                    data_age_days=age_days,
                    evidence_ref=evidence,
                )
            )

        return results
