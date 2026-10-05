"""Deterministic keyword and category matching engine for policy-to-sector rules
(Step 11, D1, D3).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from backend.app.db.models import PolicyRule
from backend.app.events.finbert import rule_based_sentiment_score


def match_headline_to_rules(
    headline: str,
    rules: Sequence[PolicyRule],
    use_sentiment: bool = True,
) -> list[tuple[PolicyRule, str, float, dict[str, Any]]]:
    """Match a news headline against active policy rules.

    Returns a list of match tuples:
        (matched_rule, affected_industry, effective_severity, evidence_dict)
    """
    clean_head = headline.strip().lower()
    matches: list[tuple[PolicyRule, str, float, dict[str, Any]]] = []

    # Optional sentiment analysis from Step 10 model
    sentiment_result = rule_based_sentiment_score(headline) if use_sentiment else None

    for rule in rules:
        # Check rule keywords
        matched_keywords: list[str] = []
        raw_keywords = rule.match_keywords if isinstance(rule.match_keywords, list) else []

        for kw in raw_keywords:
            if not isinstance(kw, str):
                continue
            clean_kw = kw.strip().lower()
            # Word boundary search or exact substring
            if len(clean_kw.split()) == 1:
                pattern = rf"\b{re.escape(clean_kw)}\b"
            else:
                pattern = re.escape(clean_kw)
            if re.search(pattern, clean_head):
                matched_keywords.append(clean_kw)

        if not matched_keywords:
            continue

        # Rule matched: generate match records for all affected industries
        industries = rule.affected_industries if isinstance(rule.affected_industries, list) else []

        for ind in industries:
            if not isinstance(ind, str):
                continue

            evidence = {
                "rule_key": rule.rule_key,
                "matched_keywords": matched_keywords,
                "headline": headline,
                "rationale": rule.rationale,
                "direction": rule.direction,
                "rule_severity": rule.severity,
                "sentiment": sentiment_result.sentiment if sentiment_result else None,
                "sentiment_p_neg": sentiment_result.p_neg if sentiment_result else None,
                "sentiment_p_pos": sentiment_result.p_pos if sentiment_result else None,
            }

            matches.append((rule, ind, rule.severity, evidence))

    return matches
