"""Fingerprint-cached explanation and glossary service."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import Explanation, GlossaryTerm, ModelConfig
from backend.app.explain import component as _component_registration  # noqa: F401
from backend.app.explain import mst as _mst_registration  # noqa: F401
from backend.app.explain import news as _news_registration  # noqa: F401
from backend.app.explain import sector as _sector_registration  # noqa: F401
from backend.app.explain.component import ComponentSubject
from backend.app.explain.guardrails import apply_payload_guardrails
from backend.app.explain.mst import MstEdgeSubject, MstNodeSubject, MstPairSubject
from backend.app.explain.news import NewsSubject
from backend.app.explain.registry import registry
from backend.app.explain.schemas import ExplanationPayload, GlossaryTermOut
from backend.app.explain.sector import DivergenceSubject, SectorSubject


class ExplanationSubjectKey(Protocol):
    @property
    def key(self) -> str: ...


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_explain_config(
    session: Session, version: str = "1.0.0", config_key: str = "explain_templates"
) -> tuple[dict[str, Any], str, str]:
    row = session.scalar(
        select(ModelConfig).where(
            ModelConfig.config_key == config_key,
            ModelConfig.version == version,
            ModelConfig.status.in_(["draft", "approved"]),
        )
    )
    if row is None:
        raise LookupError(f"{config_key} version {version} is not installed")
    return dict(row.configuration), row.version, row.configuration_hash


def get_or_create_component_explanation(
    session: Session,
    symbol: str,
    component_key: str,
    as_of: date | None = None,
    template_version: str = "1.0.0",
) -> tuple[ExplanationPayload, bool, Explanation]:
    subject = ComponentSubject(symbol=symbol.upper(), component_key=component_key)
    return get_or_create_explanation(
        session,
        subject_type="risk_component",
        subject=subject,
        as_of=as_of,
        template_version=template_version,
        config_key="explain_templates",
    )


def get_or_create_explanation(
    session: Session,
    *,
    subject_type: str,
    subject: ExplanationSubjectKey,
    as_of: date | None,
    template_version: str,
    config_key: str,
) -> tuple[ExplanationPayload, bool, Explanation]:
    explainer = registry.get(subject_type)
    config, version, config_fingerprint = load_explain_config(session, template_version, config_key)
    evidence = explainer.build_evidence(session, subject, as_of)
    if not evidence:
        raise LookupError("no stored evidence is available for this explanation")
    effective_as_of = evidence[0].as_of
    input_fingerprint = _fingerprint(
        {
            "subject": str(subject.key),
            "as_of": effective_as_of.isoformat(),
            "config_fingerprint": config_fingerprint,
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
    )
    existing = session.scalar(
        select(Explanation).where(
            Explanation.subject_type == explainer.subject_type,
            Explanation.subject_key == str(subject.key),
            Explanation.as_of == effective_as_of,
            Explanation.template_version == version,
            Explanation.input_fingerprint == input_fingerprint,
        )
    )
    if existing is not None:
        return ExplanationPayload.model_validate(existing.payload), True, existing
    payload = apply_payload_guardrails(
        explainer.compose(evidence, config, version, subject), config
    )
    payload = payload.model_copy(update={"input_fingerprint": input_fingerprint})
    row = Explanation(
        subject_type=explainer.subject_type,
        subject_key=str(subject.key),
        as_of=effective_as_of,
        template_version=version,
        config_fingerprint=config_fingerprint,
        input_fingerprint=input_fingerprint,
        payload=payload.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return payload, False, row


def get_or_create_mst_edge_explanation(
    session: Session,
    run_id: object,
    a: str,
    b: str,
    portfolio_id: object | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    from uuid import UUID

    subject = MstEdgeSubject(
        run_id=UUID(str(run_id)),
        a=a.upper(),
        b=b.upper(),
        portfolio_id=UUID(str(portfolio_id)) if portfolio_id else None,
    )
    return get_or_create_explanation(
        session,
        subject_type="mst_edge",
        subject=subject,
        as_of=None,
        template_version="1.2.0",
        config_key="mst_explain_templates",
    )


def get_or_create_mst_pair_explanation(
    session: Session,
    a: str,
    b: str,
    as_of: date | None = None,
    portfolio_id: object | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    from uuid import UUID

    subject = MstPairSubject(
        a=a.upper(),
        b=b.upper(),
        portfolio_id=UUID(str(portfolio_id)) if portfolio_id else None,
    )
    return get_or_create_explanation(
        session,
        subject_type="mst_pair",
        subject=subject,
        as_of=as_of,
        template_version="1.2.0",
        config_key="mst_explain_templates",
    )


def get_or_create_mst_node_explanation(
    session: Session,
    symbol: str,
    as_of: date | None = None,
    portfolio_id: object | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    from uuid import UUID

    subject = MstNodeSubject(
        symbol=symbol.upper(),
        portfolio_id=UUID(str(portfolio_id)) if portfolio_id else None,
    )
    return get_or_create_explanation(
        session,
        subject_type="mst_node",
        subject=subject,
        as_of=as_of,
        template_version="1.2.0",
        config_key="mst_explain_templates",
    )


def get_or_create_divergence_explanation(
    session: Session,
    symbol: str,
    as_of: date | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    return get_or_create_explanation(
        session,
        subject_type="sector_divergence",
        subject=DivergenceSubject(symbol=symbol.upper()),
        as_of=as_of,
        template_version="1.0.0",
        config_key="explain_sector_rules",
    )


def get_or_create_sector_explanation(
    session: Session,
    industry: str,
    as_of: date | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    return get_or_create_explanation(
        session,
        subject_type="sector",
        subject=SectorSubject(industry=industry.strip()),
        as_of=as_of,
        template_version="1.0.0",
        config_key="explain_sector_rules",
    )


def get_or_create_news_explanation(
    session: Session,
    news_id: object,
) -> tuple[ExplanationPayload, bool, Explanation]:
    from uuid import UUID

    return get_or_create_explanation(
        session,
        subject_type="news",
        subject=NewsSubject(news_id=UUID(str(news_id))),
        as_of=None,
        template_version="1.0.0",
        config_key="news_impact",
    )


def list_glossary(session: Session) -> list[GlossaryTermOut]:
    rows = session.scalars(
        select(GlossaryTerm).order_by(GlossaryTerm.term_key, desc(GlossaryTerm.version))
    ).all()
    latest: dict[str, GlossaryTerm] = {}
    for row in rows:
        latest.setdefault(row.term_key, row)
    return [GlossaryTermOut.model_validate(latest[key]) for key in sorted(latest)]


def get_glossary_term(session: Session, term_key: str) -> GlossaryTermOut | None:
    row = session.scalars(
        select(GlossaryTerm)
        .where(GlossaryTerm.term_key == term_key)
        .order_by(desc(GlossaryTerm.version))
    ).first()
    return GlossaryTermOut.model_validate(row) if row is not None else None
