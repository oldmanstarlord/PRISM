"""Evidence-bound explanation of stored Step E4 news impacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import NewsImpact, NewsItem, PolicyEvent, PolicyRule
from backend.app.explain.evidence import Evidence
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationConfidence,
    ExplanationDataAge,
    ExplanationPayload,
    ExplanationSection,
    ExplanationSentence,
    ExplanationSubject,
)
from backend.app.news_impact.math import historical_reaction_label
from backend.app.news_impact.service import _aggregate_rows


@dataclass(frozen=True)
class NewsSubject:
    news_id: UUID

    @property
    def key(self) -> str:
        return str(self.news_id)


def _sentence(text: str, *evidence_ids: str) -> ExplanationSentence:
    return ExplanationSentence(text=text, evidence_ids=list(evidence_ids))


class NewsExplainer:
    subject_type = "news"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, NewsSubject):
            raise TypeError("news explainer requires NewsSubject")
        impact = session.scalar(
            select(NewsImpact)
            .where(NewsImpact.news_item_id == subject.news_id, NewsImpact.status == "completed")
            .order_by(NewsImpact.created_at.desc())
        )
        news = session.get(NewsItem, subject.news_id)
        if impact is None or news is None:
            return []
        effective_as_of = news.published_at.date()
        age = max(0, (datetime.now(UTC).date() - effective_as_of).days)
        evidence = [
            Evidence(
                evidence_id="news:item",
                kind="event",
                label="News item",
                value=json.dumps(
                    {
                        "headline": news.headline,
                        "source": news.source,
                        "published_at": news.published_at.isoformat(),
                        "url": news.url,
                    },
                    sort_keys=True,
                ),
                unit=None,
                window=None,
                source_table="news_item",
                source_ref=str(news.id),
                as_of=effective_as_of,
                data_age_days=age,
            )
        ]
        rules = session.scalars(
            select(PolicyRule)
            .join(PolicyEvent, PolicyEvent.rule_id == PolicyRule.id)
            .where(PolicyEvent.news_item_id == news.id)
            .order_by(PolicyRule.rule_key)
        ).all()
        for index, rule in enumerate(rules):
            evidence.append(
                Evidence(
                    evidence_id=f"rule:{index}",
                    kind="rule",
                    label=f"Matched rule {rule.rule_key}",
                    value=json.dumps(
                        {
                            "rule_key": rule.rule_key,
                            "rationale": rule.rationale,
                            "reviewer": rule.reviewer,
                            "version": rule.version,
                            "unreviewed": not rule.reviewer.strip()
                            or rule.reviewer.strip().upper() == "UNREVIEWED",
                        },
                        sort_keys=True,
                    ),
                    source_table="policy_rule",
                    source_ref=str(rule.id),
                    as_of=effective_as_of,
                    data_age_days=age,
                )
            )
        for index, stock in enumerate(_aggregate_rows(session, impact, 0.0)):
            evidence.append(
                Evidence(
                    evidence_id=f"impact:{index}",
                    kind="statistic",
                    label=f"Impact path for {stock.symbol or stock.industry}",
                    value=stock.model_dump_json(),
                    unit="0-1 exposure",
                    window="configured recency half-life",
                    source_table="news_impact_item",
                    source_ref=str(impact.id),
                    as_of=effective_as_of,
                    data_age_days=age,
                )
            )
        rule_ids = [rule.id for rule in rules]
        analogue_count = 0
        if rule_ids:
            analogue_count = int(
                session.scalar(
                    select(func.count(func.distinct(PolicyEvent.news_item_id)))
                    .join(NewsItem, NewsItem.id == PolicyEvent.news_item_id)
                    .where(
                        PolicyEvent.rule_id.in_(rule_ids), NewsItem.published_at < news.published_at
                    )
                )
                or 0
            )
        evidence.append(
            Evidence(
                evidence_id="history:analogues",
                kind="statistic",
                label="Earlier matching items",
                value=analogue_count,
                unit="items",
                window="before this item",
                source_table="policy_event",
                source_ref=str(news.id),
                as_of=effective_as_of,
                data_age_days=age,
            )
        )
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, object],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, NewsSubject):
            raise TypeError("news explainer requires NewsSubject")
        news = json.loads(
            str(next(item.value for item in evidence if item.evidence_id == "news:item"))
        )
        rules = [item for item in evidence if item.evidence_id.startswith("rule:")]
        impacts = [item for item in evidence if item.evidence_id.startswith("impact:")]
        rows = [json.loads(str(item.value)) for item in impacts]
        minimum = int(str(config["historical_min_analogues"]))
        analogue = next(item for item in evidence if item.evidence_id == "history:analogues")
        history_text = historical_reaction_label(int(analogue.value or 0), minimum)
        impact_ids = [item.evidence_id for item in impacts] or ["news:item"]
        why = []
        for item in impacts:
            row = json.loads(str(item.value))
            path_names = ", ".join(path["path_type"] for path in row["paths"])
            why.append(
                _sentence(
                    f"{row['symbol'] or row['industry']} has stored {path_names} "
                    f"transmission evidence; its displayed exposure is "
                    f"{row['exposure_score']:.3f} using MAX across paths.",
                    item.evidence_id,
                )
            )
        configured_considerations = config["considerations"]
        if not isinstance(configured_considerations, list):
            raise ValueError("news impact considerations must be a list")
        considerations = [_sentence(str(text), *impact_ids) for text in configured_considerations]
        confidence_value = max((float(row["confidence"]) for row in rows), default=0.0)
        confidence_level = (
            "high" if confidence_value >= 0.8 else "medium" if confidence_value >= 0.5 else "low"
        )
        matched = (
            ", ".join(json.loads(str(item.value))["rule_key"] for item in rules)
            or "no stored policy rule"
        )
        age = evidence[0].data_age_days
        configured_limitations = config.get("limitations")
        limitations = (
            [str(item) for item in configured_limitations]
            if isinstance(configured_limitations, list)
            else [
                "Possible effects come from versioned rules and stored statistical relationships; "
                "they are not predictions or investment advice.",
                "Rules marked UNREVIEWED receive lower confidence.",
                "Co-movement and shared clusters do not prove a business relationship or "
                "causation.",
                "Prices are end-of-day, not real-time.",
            ]
        )
        disclaimer = str(
            config.get(
                "disclaimer",
                "PRISM provides descriptive risk explanations, not investment advice or price "
                "predictions.",
            )
        )
        return ExplanationPayload(
            headline=f"Possible transmission paths for: {news['headline']}",
            summary_points=[
                _sentence(
                    f"{news['source']} published this item at {news['published_at']}; "
                    f"matched rules: {matched}.",
                    "news:item",
                    *(item.evidence_id for item in rules),
                )
            ],
            sections=[
                ExplanationSection(
                    key="what_happened",
                    title="What happened",
                    sentences=[
                        _sentence(
                            f"Stored headline: {news['headline']} Source link: {news['url']}",
                            "news:item",
                        )
                    ],
                ),
                ExplanationSection(
                    key="who_may_be_affected",
                    title="Who may be affected",
                    sentences=[
                        _sentence(
                            f"{len(rows)} displayed stock or industry rows meet the "
                            "evidence threshold.",
                            *impact_ids,
                        )
                    ],
                    chart_spec={"type": "affected_stocks_table", "rows": rows},
                ),
                ExplanationSection(key="why", title="Why", sentences=why),
                ExplanationSection(
                    key="how_large",
                    title="How large",
                    sentences=[
                        _sentence(
                            "Exposure uses severity/10 × path weight × recency decay × "
                            "signal strength, capped at 1; multiple paths use MAX.",
                            *impact_ids,
                        ),
                        _sentence(history_text, "history:analogues"),
                    ],
                ),
                ExplanationSection(
                    key="what_to_consider", title="What to consider", sentences=considerations
                ),
            ],
            evidence=evidence,
            limitations=limitations,
            confidence=ExplanationConfidence(
                level=confidence_level,
                reasons=[
                    _sentence(
                        f"Highest stored path confidence is {confidence_value:.2f}.", *impact_ids
                    )
                ],
            ),
            data_age=ExplanationDataAge(days=age, as_of=evidence[0].as_of, status="available"),
            template_version=template_version,
            subject=ExplanationSubject(type="news", key=str(subject.news_id)),
            effective_time=evidence[0].as_of,
            method="rule-and-statistical-transmission-paths",
            method_version="1.0.0",
            lookback={"historical_analogues": "strictly earlier items"},
            units={"exposure": "0-1", "severity": "1-10", "confidence": "0-1"},
            thresholds={
                "minimum_confidence_to_display": config["minimum_confidence_to_display"],
                "spillover_min_r_squared": config["spillover_min_r_squared"],
                "historical_min_analogues": minimum,
            },
            data_sufficiency="sufficient" if impacts else "no_affected_rows",
            computed_at=datetime.now(UTC),
            disclaimer=disclaimer,
        )


registry.register(NewsExplainer())
