"""News & Policy Pressure component (dimension: macro, Step 11, D1, D2)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models import PolicyEvent, PolicyRule
from backend.app.risk_score.components.base import ComponentValue, RiskContext


class NewsPolicyPressureComponent:
    """Recency-decayed policy headwind pressure for stock industry transmission."""

    key = "news_policy_pressure"
    component_id = "news_policy_pressure"
    dimension = "macro"
    direction = "higher_is_riskier"
    required_inputs = ["news_item", "policy_rule", "policy_event"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        session = context.session
        cfg = context.config.get("news_policy_pressure", {})
        half_life_days = float(cfg.get("recency_half_life_days", 14))
        tailwind_cap = float(cfg.get("tailwind_mitigation_cap", 0.30))

        # Query all policy events up to data_cutoff and as_of
        stmt = (
            select(PolicyEvent, PolicyRule)
            .join(PolicyRule, PolicyEvent.rule_id == PolicyRule.id)
            .where(
                PolicyEvent.matched_at <= context.data_cutoff,
            )
            .order_by(PolicyEvent.matched_at.desc())
        )

        rows = session.execute(stmt).all()

        # Group policy events by affected_industry
        events_by_industry: dict[str, list[tuple[PolicyEvent, PolicyRule]]] = {}
        for pe, pr in rows:
            if pe.matched_at.date() <= as_of:
                events_by_industry.setdefault(pe.affected_industry, []).append((pe, pr))

        results: list[ComponentValue] = []

        for sec_id, symbol, industry in universe:
            items = events_by_industry.get(industry, [])

            if not items:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=0.0,
                        status="ok",
                        data_as_of=as_of,
                        data_age_days=0,
                        evidence_ref={
                            "industry": industry,
                            "matched_policy_count": 0,
                            "gross_headwind_pressure": 0.0,
                            "tailwind_mitigation": 0.0,
                            "net_pressure": 0.0,
                            "headline": f"No adverse policy actions identified for {industry}.",
                        },
                    )
                )
                continue

            gross_headwind = 0.0
            gross_tailwind = 0.0
            headwind_count = 0
            tailwind_count = 0
            latest_matched_at = items[0][0].matched_at.date()
            most_recent_headline = items[0][0].evidence.get("headline", "Policy action")

            for pe, pr in items:
                days_elapsed = max(0, (as_of - pe.matched_at.date()).days)
                decay = 2.0 ** (-days_elapsed / half_life_days)

                if pr.direction == "headwind":
                    gross_headwind += pe.severity * decay
                    headwind_count += 1
                elif pr.direction == "tailwind":
                    gross_tailwind += pe.severity * decay
                    tailwind_count += 1

            # Cap tailwind mitigation
            allowed_mitigation = min(gross_tailwind, gross_headwind * tailwind_cap)
            net_pressure = max(0.0, gross_headwind - allowed_mitigation)
            data_age = max(0, (as_of - latest_matched_at).days)

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(net_pressure, 4),
                    status="ok",
                    data_as_of=latest_matched_at,
                    data_age_days=data_age,
                    evidence_ref={
                        "industry": industry,
                        "matched_policy_count": len(items),
                        "headwind_count": headwind_count,
                        "tailwind_count": tailwind_count,
                        "gross_headwind_pressure": round(gross_headwind, 2),
                        "gross_tailwind": round(gross_tailwind, 2),
                        "allowed_mitigation": round(allowed_mitigation, 2),
                        "net_pressure": round(net_pressure, 2),
                        "headline": most_recent_headline,
                        "rule_key": items[0][1].rule_key,
                        "rationale": items[0][1].rationale,
                    },
                )
            )

        return results
