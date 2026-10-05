"""Event Risk Pressure component (dimension: events, D2)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models import EventItem, TextScore
from backend.app.risk_score.components.base import ComponentValue, RiskContext


class EventRiskPressureComponent:
    """Recency-decayed risk pressure from corporate announcements and text intelligence."""

    key = "event_risk_pressure"
    dimension = "events"
    direction = "higher_is_riskier"
    required_inputs = ["event_item", "event_rule", "text_score"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        session = context.session
        cfg = context.config.get("event_risk_pressure", {})
        half_life_days = float(cfg.get("recency_half_life_days", 14))
        positive_offset_cap = float(cfg.get("positive_offset_cap", 0.30))

        sec_ids = [u[0] for u in universe]

        # Query all relevant announcements up to cutoff
        query = (
            select(EventItem, TextScore)
            .outerjoin(TextScore, EventItem.id == TextScore.item_id)
            .where(
                EventItem.security_id.in_(sec_ids),
                EventItem.published_at <= context.data_cutoff,
                EventItem.effective_trading_date <= as_of,
            )
            .order_by(EventItem.effective_trading_date.desc())
        )

        rows = session.execute(query).all()

        events_by_sec: dict[UUID, list[tuple[EventItem, TextScore | None]]] = {}
        for ev, score in rows:
            events_by_sec.setdefault(ev.security_id, []).append((ev, score))

        results: list[ComponentValue] = []

        for sec_id, symbol, _ in universe:
            items = events_by_sec.get(sec_id, [])

            if not items:
                # No recent announcements: baseline 0 pressure
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
                            "event_count": 0,
                            "neg_pressure": 0.0,
                            "pos_mitigation": 0.0,
                            "net_pressure": 0.0,
                            "headline": "No material event announcements in recent window.",
                        },
                    )
                )
                continue

            # Calculate recency-decayed pressure
            neg_pressure = 0.0
            pos_mitigation = 0.0
            neg_count = 0
            pos_count = 0
            most_recent_headline = items[0][0].headline
            latest_eff_date = items[0][0].effective_trading_date

            for ev, score in items:
                # Calendar days elapsed since effective trading date
                days_elapsed = max(0, (as_of - ev.effective_trading_date).days)
                # Recency decay: 2^(-delta / half_life)
                decay = 2.0 ** (-days_elapsed / half_life_days)

                sentiment = score.sentiment if score else "negative"

                if sentiment == "negative":
                    neg_pressure += ev.importance * decay
                    neg_count += 1
                elif sentiment == "positive":
                    pos_mitigation += ev.importance * decay
                    pos_count += 1

            # Cap positive offset (cannot erase more than positive_offset_cap of negative risk)
            max_offset = neg_pressure * positive_offset_cap
            allowed_offset = min(pos_mitigation, max_offset)
            net_pressure = max(0.0, neg_pressure - allowed_offset)

            data_age = max(0, (as_of - latest_eff_date).days)

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(net_pressure, 4),
                    status="ok",
                    data_as_of=latest_eff_date,
                    data_age_days=data_age,
                    evidence_ref={
                        "event_count": len(items),
                        "neg_events": neg_count,
                        "pos_events": pos_count,
                        "gross_negative_pressure": round(neg_pressure, 2),
                        "positive_mitigation": round(pos_mitigation, 2),
                        "allowed_positive_offset": round(allowed_offset, 2),
                        "net_pressure": round(net_pressure, 2),
                        "headline": most_recent_headline,
                    },
                )
            )

        return results
