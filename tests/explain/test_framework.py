from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Explanation,
    ModelConfig,
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    Security,
    SecurityAlias,
    StockRiskResult,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import (
    apply_payload_guardrails,
    evidence_bound_sentences,
    validate_text,
)
from backend.app.explain.schemas import (
    ExplanationConfidence,
    ExplanationDataAge,
    ExplanationPayload,
    ExplanationSection,
    ExplanationSentence,
    ExplanationSubject,
)
from backend.app.explain.service import get_or_create_component_explanation
from backend.app.explain.templates import build_sentence
from backend.app.main import app


def _seed_component_run(
    session: Session,
    *,
    symbol: str = "E1TEST",
    as_of: date = date(2026, 9, 30),
    raw_value: Decimal | None = Decimal("0.24000000"),
    percentile_rank: Decimal | None = Decimal("82.5000"),
    points: Decimal | None = Decimal("82.5000"),
    status: str = "ok",
) -> tuple[ScoreComponentValue, ScoreComponentDefinition]:
    security_id = uuid4()
    session.add(
        Security(
            id=security_id,
            isin=f"INE{str(security_id.int)[-9:]}",
            company_name="E1 Test Limited",
            sector="Test",
            industry="Test",
            is_active=True,
        )
    )
    session.flush()
    session.add(
        SecurityAlias(
            id=uuid4(),
            security_id=security_id,
            symbol=symbol,
            exchange="NSE",
            valid_from=date(2020, 1, 1),
            source="TEST",
            ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    session.flush()
    definition = session.scalar(
        select(ScoreComponentDefinition).where(
            ScoreComponentDefinition.component_id == "ewma_volatility"
        )
    )
    assert definition is not None
    config_id = uuid4()
    session.add(
        ModelConfig(
            id=config_id,
            config_key=f"e1_test_risk_{uuid4()}",
            version="1.0.0",
            status="draft",
            configuration={"component_weights": {"ewma_volatility": 1.25}},
            configuration_hash="1" * 64,
        )
    )
    session.flush()
    run_id = uuid4()
    session.add(
        ScoreRun(
            id=run_id,
            as_of_date=as_of,
            data_cutoff=datetime(as_of.year, as_of.month, as_of.day, 23, 59, tzinfo=UTC),
            model_config_id=config_id,
            config_version="1.0.0",
            config_fingerprint=str(uuid4()).replace("-", "") * 2,
            input_fingerprint=str(uuid4()).replace("-", "") * 2,
            status="completed",
            total_securities=1,
            scored_securities=1,
            started_at=datetime(2026, 10, 1, tzinfo=UTC),
            completed_at=datetime(2026, 10, 1, 0, 1, tzinfo=UTC),
        )
    )
    session.flush()
    session.add(
        StockRiskResult(
            id=uuid4(),
            run_id=run_id,
            security_id=security_id,
            symbol=symbol,
            total_score=Decimal("61.0"),
            confidence=Decimal("88.0"),
            data_coverage=Decimal("1.0"),
            dimension_scores={},
            top_reasons=[],
            limitations=[],
            computed_at=datetime(2026, 10, 1, 0, 2, tzinfo=UTC),
        )
    )
    session.flush()
    value = ScoreComponentValue(
        id=uuid4(),
        run_id=run_id,
        security_id=security_id,
        component_id="ewma_volatility",
        raw_value=raw_value,
        percentile_rank=percentile_rank,
        points=points,
        status=status,
        data_as_of=as_of,
        data_age_days=0,
        evidence_ref={"observations": 60, "unit": "annualised decimal"},
    )
    session.add(value)
    session.flush()
    return value, definition


def test_unsupported_sentence_is_dropped_and_banned_template_fails() -> None:
    config = {
        "banned_phrases": ["buy", "price target"],
        "correlation_required_phrase": "moves together with",
    }
    supported = ExplanationSentence(text="Stored value is 4.", evidence_ids=["e1"])
    unsupported = ExplanationSentence(text="Unsupported text.", evidence_ids=["missing"])
    assert evidence_bound_sentences([supported, unsupported], {"e1"}, config) == [supported]
    with pytest.raises(ValueError, match="banned phrase"):
        build_sentence("You should buy this stock.", {}, ["e1"], config)


def test_correlation_wording_rule() -> None:
    config = {
        "banned_phrases": [],
        "correlation_required_phrase": "moves together with",
    }
    with pytest.raises(ValueError, match="correlation wording"):
        validate_text("Correlation is strong.", config)
    validate_text(
        "The asset moves together with the benchmark; stored correlation is strong.", config
    )


def test_payload_guardrails_require_limitations_and_disclaimer() -> None:
    evidence = Evidence(
        evidence_id="e1",
        kind="statistic",
        label="Stored fact",
        value=1,
        source_table="test_table",
        source_ref="row:field",
        as_of=date(2026, 1, 1),
    )
    payload = ExplanationPayload(
        headline="Stored explanation",
        summary_points=[ExplanationSentence(text="Supported.", evidence_ids=["e1"])],
        sections=[
            ExplanationSection(
                key="test",
                title="Test",
                sentences=[ExplanationSentence(text="Unsupported.", evidence_ids=["missing"])],
            )
        ],
        evidence=[evidence],
        limitations=[],
        confidence=ExplanationConfidence(level="high", reasons=[]),
        data_age=ExplanationDataAge(days=0, as_of=date(2026, 1, 1), status="ok"),
        template_version="1.0.0",
        subject=ExplanationSubject(type="test", key="test"),
        disclaimer="",
    )
    guarded = apply_payload_guardrails(
        payload,
        {
            "banned_phrases": [],
            "correlation_required_phrase": "moves together with",
            "limitations": ["Stored evidence only."],
            "disclaimer": "Not investment advice.",
        },
    )
    assert guarded.sections[0].sentences == []
    assert guarded.limitations == ["Stored evidence only."]
    assert guarded.disclaimer == "Not investment advice."


def test_component_evidence_equals_source_rows_and_cache_is_idempotent(
    session: Session,
) -> None:
    value, definition = _seed_component_run(session)
    before = session.scalar(select(func.count(Explanation.id))) or 0
    first, first_reused, first_row = get_or_create_component_explanation(
        session, "E1TEST", "ewma_volatility"
    )
    second, second_reused, second_row = get_or_create_component_explanation(
        session, "E1TEST", "ewma_volatility"
    )
    after = session.scalar(select(func.count(Explanation.id))) or 0
    assert first_reused is False
    assert second_reused is True
    assert first_row.id == second_row.id
    assert first == second
    assert after == before + 1

    by_label = {item.label: item for item in first.evidence}
    assert by_label["Component label"].value == definition.name
    assert by_label["Raw value"].value == float(value.raw_value)
    assert by_label["Percentile rank"].value == float(value.percentile_rank)
    assert by_label["Risk points"].value == float(value.points)
    assert by_label["Status"].value == value.status
    assert by_label["Data age"].value == value.data_age_days
    assert by_label["Direction"].value == definition.direction
    assert by_label["Component weight"].value == 1.25
    assert by_label["Calculation window"].value == value.evidence_ref["observations"]
    assert all(sentence.evidence_ids for sentence in first.summary_points)
    assert all(
        sentence.evidence_ids for section in first.sections for sentence in section.sentences
    )


def test_component_explainer_respects_as_of_and_missing_numeric_values(
    session: Session,
) -> None:
    old_value, _ = _seed_component_run(
        session,
        symbol="E1OLD",
        as_of=date(2026, 6, 30),
        raw_value=Decimal("0.10000000"),
    )
    old_run = session.get(ScoreRun, old_value.run_id)
    assert old_run is not None
    future_run_id = uuid4()
    session.add(
        ScoreRun(
            id=future_run_id,
            as_of_date=date(2026, 8, 31),
            data_cutoff=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
            model_config_id=old_run.model_config_id,
            config_version="1.0.0",
            config_fingerprint="2" * 64,
            input_fingerprint="3" * 64,
            status="completed",
            total_securities=1,
            scored_securities=1,
            started_at=datetime(2026, 9, 1, tzinfo=UTC),
            completed_at=datetime(2026, 9, 1, 0, 1, tzinfo=UTC),
        )
    )
    session.flush()
    session.add(
        StockRiskResult(
            id=uuid4(),
            run_id=future_run_id,
            security_id=old_value.security_id,
            symbol="E1OLD",
            total_score=Decimal("90"),
            confidence=Decimal("90"),
            data_coverage=Decimal("1"),
            dimension_scores={},
            top_reasons=[],
            limitations=[],
            computed_at=datetime(2026, 9, 1, 0, 2, tzinfo=UTC),
        )
    )
    session.flush()
    session.add(
        ScoreComponentValue(
            id=uuid4(),
            run_id=future_run_id,
            security_id=old_value.security_id,
            component_id="ewma_volatility",
            raw_value=Decimal("0.90000000"),
            percentile_rank=Decimal("99"),
            points=Decimal("99"),
            status="ok",
            data_as_of=date(2026, 8, 31),
            data_age_days=0,
            evidence_ref={"observations": 60},
        )
    )
    session.flush()
    payload, _, _ = get_or_create_component_explanation(
        session,
        "E1OLD",
        "ewma_volatility",
        as_of=date(2026, 7, 1),
    )
    assert payload.data_age.as_of == date(2026, 6, 30)
    assert next(item for item in payload.evidence if item.label == "Raw value").value == 0.1

    _seed_component_run(
        session,
        symbol="E1MISS",
        raw_value=None,
        percentile_rank=None,
        points=None,
        status="missing",
    )
    missing_payload, _, _ = get_or_create_component_explanation(
        session, "E1MISS", "ewma_volatility"
    )
    assert missing_payload.summary_points == []
    assert missing_payload.confidence.level == "low"
    assert (
        next(item for item in missing_payload.evidence if item.label == "Raw value").value is None
    )


def test_explanation_and_glossary_api(session: Session) -> None:
    _seed_component_run(session, symbol="E1API")
    client = TestClient(app)
    response = client.get("/api/v1/explain/component/E1API/ewma_volatility")
    assert response.status_code == 200
    assert response.json()["subject"]["key"] == "E1API:ewma_volatility"
    glossary = client.get("/api/v1/glossary")
    assert glossary.status_code == 200
    assert len(glossary.json()) == 25
    term = client.get("/api/v1/glossary/correlation")
    assert term.status_code == 200
    assert "move together" in term.json()["plain_definition"]
    missing = client.get("/api/v1/glossary/not_a_term")
    assert missing.status_code == 404
