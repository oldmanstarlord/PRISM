"""Golden explanation snapshot regression test suite (Step E6).

Verifies snapshot explanations for:
- 3 stocks: INFY, TCS, RELIANCE
- 3 MST edges: HDFCBANK-ICICIBANK, INFY-TCS, TATASTEEL-JSWSTEEL
- 3 news items: news_item_1, news_item_2, news_item_3

Ensures:
1. Valid schema conforming to ExplanationPayload.
2. Evidence-bound invariants: every sentence links to valid evidence IDs.
3. Wording guardrails: zero banned phrases, zero forbidden causal phrasing.
4. Non-empty limitations, disclaimer, and data_age attributes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.explain.guardrails import validate_text
from backend.app.explain.schemas import ExplanationPayload
from tests.explain.test_wording_guards import (
    BANNED_PHRASES,
    _check_text_safety,
    _collect_payload_texts,
)

GOLDEN_DIR = Path(__file__).parent.parent / "fixtures" / "golden"

EXPECTED_GOLDEN_FILES = [
    # 3 Stocks
    "INFY.json",
    "TCS.json",
    "RELIANCE.json",
    # 3 MST edges
    "edge_HDFCBANK_ICICIBANK.json",
    "edge_INFY_TCS.json",
    "edge_TATASTEEL_JSWSTEEL.json",
    # 3 News items
    "news_item_1.json",
    "news_item_2.json",
    "news_item_3.json",
]


def test_golden_directory_contains_all_required_snapshots() -> None:
    """Assert all 9 required golden explanation snapshots exist on disk."""
    assert GOLDEN_DIR.exists(), f"Golden directory not found: {GOLDEN_DIR}"
    for filename in EXPECTED_GOLDEN_FILES:
        filepath = GOLDEN_DIR / filename
        assert filepath.exists(), f"Missing required golden snapshot: {filename}"


@pytest.mark.parametrize("filename", EXPECTED_GOLDEN_FILES)
def test_golden_snapshot_schema_and_evidence_invariants(filename: str) -> None:
    """Validate ExplanationPayload schema and evidence-binding for each golden snapshot."""
    filepath = GOLDEN_DIR / filename
    raw_content = filepath.read_text(encoding="utf-8")

    # 1. Pydantic schema validation
    payload = ExplanationPayload.model_validate_json(raw_content)
    assert payload.schema_version == "1.0"
    assert payload.headline.strip()
    assert payload.disclaimer.strip()
    assert len(payload.limitations) >= 1

    # 2. Evidence validation
    valid_ids = {e.evidence_id for e in payload.evidence}
    assert len(valid_ids) >= 1, f"{filename} has no evidence items"

    # 3. Check summary points evidence-binding
    for s in payload.summary_points:
        assert s.evidence_ids, f"{filename} summary sentence lacks evidence_ids"
        for eid in s.evidence_ids:
            assert eid in valid_ids, f"{filename} references unbacked evidence '{eid}'"

    # 4. Check section sentences evidence-binding
    for sec in payload.sections:
        for s in sec.sentences:
            assert s.evidence_ids, f"{filename} section sentence lacks evidence_ids"
            for eid in s.evidence_ids:
                assert eid in valid_ids, f"{filename} references unbacked evidence '{eid}'"

    # 5. Check confidence reasons evidence-binding
    for r in payload.confidence.reasons:
        assert r.evidence_ids, f"{filename} confidence reason lacks evidence_ids"
        for eid in r.evidence_ids:
            assert eid in valid_ids, f"{filename} references unbacked evidence '{eid}'"


@pytest.mark.parametrize("filename", EXPECTED_GOLDEN_FILES)
def test_golden_snapshot_wording_guards(filename: str) -> None:
    """Assert zero banned phrases and non-causal language across all golden snapshots."""
    filepath = GOLDEN_DIR / filename
    raw_content = filepath.read_text(encoding="utf-8")
    payload = ExplanationPayload.model_validate_json(raw_content)

    config = {
        "banned_phrases": BANNED_PHRASES,
        "correlation_required_phrase": "moves together with",
    }

    # Check safety against banned phrases and forbidden causal phrasing across all text
    for text in _collect_payload_texts(payload):
        _check_text_safety(text, f"golden snapshot {filename}")

    # Validate correlation language on generated text (headline, summary, sections, reasons)
    validate_text(payload.headline, config)
    for s in payload.summary_points:
        validate_text(s.text, config)
    for sec in payload.sections:
        for s in sec.sentences:
            validate_text(s.text, config)
    for r in payload.confidence.reasons:
        validate_text(r.text, config)
