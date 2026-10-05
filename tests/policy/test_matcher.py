"""Test policy keyword matching and evidence extraction (Step 11, D1, D3)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.db.models import PolicyRule
from backend.app.policy.matcher import match_headline_to_rules


@pytest.fixture
def sample_rules() -> list[PolicyRule]:
    return [
        PolicyRule(
            id=uuid4(),
            rule_key="POL_RBI_RATE_HIKE_V1",
            description="Policy repo rate increase by RBI MPC",
            match_keywords=["repo rate", "rate hike", "monetary policy"],
            match_category="monetary",
            affected_industries=["Financial Services", "Banking", "Realty"],
            direction="headwind",
            severity=7.0,
            rationale=(
                "Elevates funding costs and increases debt service burdens on "
                "rate-sensitive sectors."
            ),
            reviewer="Lead Macro Economist",
            version="1.0.0",
            active=True,
        ),
        PolicyRule(
            id=uuid4(),
            rule_key="POL_PLI_SCHEME_EXPANSION_V1",
            description="Expansion of central Production Linked Incentive outlay",
            match_keywords=["pli scheme", "production linked incentive"],
            match_category="manufacturing",
            affected_industries=["Automobile and Auto Components", "Electronics"],
            direction="tailwind",
            severity=6.0,
            rationale=(
                "Direct cash incentives for incremental domestic manufacturing "
                "enhance margin profile."
            ),
            reviewer="Policy Specialist",
            version="1.0.0",
            active=True,
        ),
    ]


def test_matcher_detects_headwind_and_produces_evidence(sample_rules: list[PolicyRule]):
    headline = "Monetary Policy Committee raises Repo Rate by 25 bps to curb inflation"
    matches = match_headline_to_rules(headline, sample_rules, use_sentiment=False)

    assert len(matches) == 3  # 3 affected industries: Financial Services, Banking, Realty
    rule, ind, sev, evidence = matches[0]

    assert rule.rule_key == "POL_RBI_RATE_HIKE_V1"
    assert sev == 7.0
    assert ind in ["Financial Services", "Banking", "Realty"]
    matched_kws = evidence["matched_keywords"]
    assert "repo rate" in matched_kws or "monetary policy" in matched_kws
    assert evidence["direction"] == "headwind"
    assert "Elevates funding costs" in evidence["rationale"]


def test_matcher_detects_tailwind(sample_rules: list[PolicyRule]):
    headline = "Union Cabinet approves Rs 10,000 crore expansion for PLI scheme in electronics"
    matches = match_headline_to_rules(headline, sample_rules, use_sentiment=False)

    assert len(matches) == 2  # Automobile and Auto Components, Electronics
    rule, ind, sev, evidence = matches[0]

    assert rule.rule_key == "POL_PLI_SCHEME_EXPANSION_V1"
    assert sev == 6.0
    assert evidence["direction"] == "tailwind"
    assert "pli scheme" in evidence["matched_keywords"]


def test_matcher_ignores_unrelated_news(sample_rules: list[PolicyRule]):
    headline = "Cricket board announces schedule for upcoming championship trophy"
    matches = match_headline_to_rules(headline, sample_rules, use_sentiment=False)
    assert len(matches) == 0
