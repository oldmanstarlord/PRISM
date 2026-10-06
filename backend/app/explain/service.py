"""Fingerprint-cached explanation and glossary service."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Explanation,
    GlossaryTerm,
    ModelConfig,
    NewsItem,
    SecurityAlias,
)
from backend.app.explain import alert as _alert_registration  # noqa: F401
from backend.app.explain import component as _component_registration  # noqa: F401
from backend.app.explain import diversification as _diversification_registration  # noqa: F401
from backend.app.explain import mst as _mst_registration  # noqa: F401
from backend.app.explain import news as _news_registration  # noqa: F401
from backend.app.explain import score_change as _score_change_registration  # noqa: F401
from backend.app.explain import sector as _sector_registration  # noqa: F401
from backend.app.explain import shock as _shock_registration  # noqa: F401
from backend.app.explain.alert import AlertSubject
from backend.app.explain.component import ComponentSubject
from backend.app.explain.diversification import DiversificationSubject
from backend.app.explain.guardrails import apply_payload_guardrails
from backend.app.explain.mst import MstEdgeSubject, MstNodeSubject, MstPairSubject
from backend.app.explain.news import NewsSubject
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationPayload,
    ExplanationSearchResult,
    ExplanationSummaryOut,
    GlossaryTermOut,
)
from backend.app.explain.score_change import ScoreChangeSubject
from backend.app.explain.sector import DivergenceSubject, SectorSubject
from backend.app.explain.shock import ShockSubject


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
    config, version, config_fingerprint = load_explain_config(
        session, template_version, config_key
    )
    cached_query = select(Explanation).where(
        Explanation.subject_type == explainer.subject_type,
        Explanation.subject_key == str(subject.key),
        Explanation.template_version == version,
        Explanation.config_fingerprint == config_fingerprint,
    )
    if as_of is not None:
        cached_query = cached_query.where(Explanation.as_of == as_of)
    cached_row = session.scalar(
        cached_query.order_by(desc(Explanation.created_at)).limit(1)
    )
    if cached_row is not None:
        return (
            ExplanationPayload.model_validate(cached_row.payload),
            True,
            cached_row,
        )

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


def get_or_create_mst_edge_explanation(
    session: Session,
    run_id: object,
    a: str,
    b: str,
    portfolio_id: object | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
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
    return get_or_create_explanation(
        session,
        subject_type="news",
        subject=NewsSubject(news_id=UUID(str(news_id))),
        as_of=None,
        template_version="1.0.0",
        config_key="news_impact",
    )


def get_or_create_shock_explanation(
    session: Session,
    holding_symbol: str,
    shocked_symbol: str,
    portfolio_id: object | None = None,
    scenario_id: object | None = None,
    shock_pct: float = -10.0,
    method: str = "regression_beta",
) -> tuple[ExplanationPayload, bool, Explanation]:
    subject = ShockSubject(
        holding_symbol=holding_symbol.upper(),
        shocked_symbol=shocked_symbol.upper(),
        portfolio_id=UUID(str(portfolio_id)) if portfolio_id else None,
        scenario_id=UUID(str(scenario_id)) if scenario_id else None,
        shock_pct=float(shock_pct),
        method=method,
    )
    return get_or_create_explanation(
        session,
        subject_type="shock",
        subject=subject,
        as_of=None,
        template_version="1.0.0",
        config_key="explain_extended_templates",
    )


def get_or_create_diversification_explanation(
    session: Session,
    portfolio_id: object,
    run_id: object | None = None,
    as_of: date | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    subject = DiversificationSubject(
        portfolio_id=UUID(str(portfolio_id)),
        run_id=UUID(str(run_id)) if run_id else None,
    )
    return get_or_create_explanation(
        session,
        subject_type="diversification",
        subject=subject,
        as_of=as_of,
        template_version="1.0.0",
        config_key="explain_extended_templates",
    )


def get_or_create_score_change_explanation(
    session: Session,
    symbol: str,
    as_of: date | None = None,
) -> tuple[ExplanationPayload, bool, Explanation]:
    subject = ScoreChangeSubject(
        symbol=symbol.upper(),
        as_of=as_of,
    )
    return get_or_create_explanation(
        session,
        subject_type="score_change",
        subject=subject,
        as_of=as_of,
        template_version="1.0.0",
        config_key="explain_extended_templates",
    )


def get_or_create_alert_explanation(
    session: Session,
    alert_id: object,
) -> tuple[ExplanationPayload, bool, Explanation]:
    subject = AlertSubject(alert_id=UUID(str(alert_id)))
    return get_or_create_explanation(
        session,
        subject_type="alert",
        subject=subject,
        as_of=None,
        template_version="1.0.0",
        config_key="explain_extended_templates",
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


def _format_request_path(subject_type: str, subject_key: str) -> str:
    if subject_type == "risk_component" and ":" in subject_key:
        sym, comp = subject_key.split(":", 1)
        return f"/explain/component/{sym}/{comp}"
    if subject_type == "sector_divergence":
        return f"/explain/divergence/{subject_key}"
    if subject_type == "sector":
        return f"/explain/sector/{subject_key}"
    if subject_type == "mst_node":
        return f"/explain/mst/node/{subject_key}"
    if subject_type == "mst_pair" and ":" in subject_key:
        pair_part = subject_key.split(":")[-1]
        if "<->" in pair_part:
            a, b = pair_part.split("<->")
            return f"/explain/mst/pair?a={a}&b={b}"
    if subject_type == "mst_edge" and ":" in subject_key:
        parts = subject_key.split(":")
        run_id = parts[0]
        edge_part = parts[-1]
        if "-" in edge_part:
            a, b = edge_part.split("-")
            return f"/explain/mst/edge?run_id={run_id}&a={a}&b={b}"
    if subject_type == "news":
        return f"/explain/news/{subject_key}"
    if subject_type == "shock":
        # global:INFY->TCS:-10.00:regression_beta
        parts = subject_key.split(":")
        port_id = parts[0] if parts[0] != "global" else None
        pair = parts[1]
        shock_pct = parts[2] if len(parts) > 2 else "-10"
        method = parts[3] if len(parts) > 3 else "regression_beta"
        if "->" in pair:
            shocked, holding = pair.split("->")
            url = (
                f"/explain/shock?holding_symbol={holding}&shocked_symbol={shocked}"
                f"&shock_pct={shock_pct}&method={method}"
            )
            if port_id:
                url += f"&portfolio_id={port_id}"
            return url
    if subject_type == "diversification":
        port_id = subject_key.replace("portfolio:", "")
        return f"/explain/diversification/{port_id}"
    if subject_type == "score_change":
        sym = subject_key.split(":")[0]
        return f"/explain/score-change/{sym}"
    if subject_type == "alert":
        alert_id = subject_key.replace("alert:", "")
        return f"/explain/alert/{alert_id}"
    return f"/explain/detail?type={subject_type}&key={subject_key}"


def list_recent_explanations(session: Session, limit: int = 50) -> list[ExplanationSummaryOut]:
    rows = session.scalars(
        select(Explanation).order_by(desc(Explanation.created_at)).limit(limit)
    ).all()
    results: list[ExplanationSummaryOut] = []
    for r in rows:
        payload = dict(r.payload)
        headline = str(payload.get("headline", r.subject_key))
        conf_obj = payload.get("confidence", {})
        conf_level = conf_obj.get("level", "medium") if isinstance(conf_obj, dict) else "medium"
        results.append(
            ExplanationSummaryOut(
                id=str(r.id),
                subject_type=r.subject_type,
                subject_key=r.subject_key,
                as_of=r.as_of,
                template_version=r.template_version,
                headline=headline,
                confidence_level=conf_level,
                created_at=r.created_at,
                request_path=_format_request_path(r.subject_type, r.subject_key),
            )
        )
    return results


def search_explanations(
    session: Session, query: str, limit: int = 25
) -> list[ExplanationSearchResult]:
    q = query.strip()
    if not q:
        return []

    results: list[ExplanationSearchResult] = []
    seen_paths: set[str] = {} if False else set()

    # 1. Check if pair query e.g. "TCS, INFY" or "TCS-INFY"
    for sep in [",", "-", "/", " "]:
        if sep in q:
            tokens = [t.strip().upper() for t in q.split(sep) if t.strip()]
            if len(tokens) == 2 and tokens[0] != tokens[1]:
                sym_a, sym_b = tokens
                path = f"/explain/mst/pair?a={sym_a}&b={sym_b}"
                results.append(
                    ExplanationSearchResult(
                        category="pair",
                        title=f"{sym_a} ↔ {sym_b}",
                        subtitle=f"Co-movement and MST tree distance between {sym_a} and {sym_b}",
                        path=path,
                    )
                )
                seen_paths.add(path)
                break

    # 2. Stock symbol search
    stock_aliases = session.scalars(
        select(SecurityAlias)
        .where(func.upper(SecurityAlias.symbol).like(f"%{q.upper()}%"))
        .limit(5)
    ).all()
    for sa in stock_aliases:
        sym = sa.symbol.upper()
        # Score change path
        p_sc = f"/explain/score-change/{sym}"
        if p_sc not in seen_paths:
            results.append(
                ExplanationSearchResult(
                    category="stock",
                    title=f"{sym} Score Trajectory",
                    subtitle=f"Multidimensional risk score change and component shifts for {sym}",
                    path=p_sc,
                )
            )
            seen_paths.add(p_sc)
        # Divergence path
        p_div = f"/explain/divergence/{sym}"
        if p_div not in seen_paths:
            results.append(
                ExplanationSearchResult(
                    category="stock",
                    title=f"{sym} Sector Divergence",
                    subtitle=f"Layer 1 peer divergence and residual direction for {sym}",
                    path=p_div,
                )
            )
            seen_paths.add(p_div)

    # 3. News items
    news_items = session.scalars(
        select(NewsItem)
        .where(
            or_(
                func.lower(NewsItem.headline).like(f"%{q.lower()}%"),
                func.lower(NewsItem.source).like(f"%{q.lower()}%"),
            )
        )
        .order_by(desc(NewsItem.published_at))
        .limit(5)
    ).all()
    for ni in news_items:
        p_news = f"/explain/news/{ni.id}"
        if p_news not in seen_paths:
            results.append(
                ExplanationSearchResult(
                    category="news",
                    title=ni.headline[:80],
                    subtitle=f"Impact transmission: {ni.source}",
                    path=p_news,
                )
            )
            seen_paths.add(p_news)

    # 4. Search existing stored explanations by subject_key
    expl_key_rows = session.scalars(
        select(Explanation)
        .where(func.lower(Explanation.subject_key).like(f"%{q.lower()}%"))
        .order_by(desc(Explanation.created_at))
        .limit(5)
    ).all()
    for er in expl_key_rows:
        path = _format_request_path(er.subject_type, er.subject_key)
        if path not in seen_paths:
            payload = dict(er.payload)
            headline = str(payload.get("headline", er.subject_key))
            results.append(
                ExplanationSearchResult(
                    category="recent",
                    title=headline,
                    subtitle=f"{er.subject_type}: {er.subject_key} · {er.as_of}",
                    path=path,
                    explanation_id=str(er.id),
                )
            )
            seen_paths.add(path)

    return results[:limit]
