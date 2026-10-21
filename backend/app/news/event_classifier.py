"""Corporate event classification for financial news intelligence."""

from __future__ import annotations

import re

from backend.app.news.schemas import EventCategory

EVENT_PATTERNS: dict[EventCategory, list[str]] = {
    "earnings": [
        r"\b(q[1-4]|quarterly|annual|full[- ]year)\s+(results|profit|revenue|loss|ebitda)\b",
        r"\b(net profit|pat|ebitda|topline)\s+(surges|plunges|rises|falls|beats|misses)\b",
        r"\b(revenue)\s+(surges|plunges|rises|falls|beats|misses|grows)\b",
        r"\b(earnings|quarterly report|financial results)\b",
    ],
    "guidance": [
        r"\b(guidance|outlook|forward target|fy2[5-7] target|forecast|margin target)\b",
        r"\b(lowers guidance|raises guidance|maintains outlook|growth forecast)\b",
    ],
    "dividend": [
        r"\b(dividend|interim dividend|special dividend|dividend payout|bonus issue|stock split)\b",
        r"\b(record date for dividend|board declares dividend)\b",
    ],
    "m&a": [
        r"\b(acquisition|acquires|to acquire|merger|merges with|buyout|takeover)\b",
        r"\b(stake buy|stake sale|divestment|joint venture|jv|amalgamation)\b",
    ],
    "regulation": [
        r"\b(sebi|rbi|cci|regulatory|compliance|penalty by sebi|show-cause notice)\b",
        r"\b(licence approval|rbi guidelines|policy mandate|regulatory probe)\b",
    ],
    "litigation": [
        r"\b(lawsuit|nclt|court|high court|supreme court|legal dispute|litigation)\b",
        r"\b(arbitration|fraud case|stay order|tax tribunal|inquiry into)\b",
    ],
    "product": [
        r"\b(launches|new product|commercial rollout|order win|contract win|bags order)\b",
        r"\b(commissions plant|new facility|expansion project|secures contract)\b",
    ],
    "macro": [
        r"\b(rbi repo rate|monetary policy|inflation|cpi|gdp growth|fiscal deficit)\b",
        r"\b(rupee slides|rupee surges|us fed|crude oil prices|sovereign bond)\b",
    ],
}


class EventClassifier:
    """Classifies news headlines and text into structured financial event categories."""

    def classify(self, text: str) -> tuple[EventCategory, float]:
        """Classify event category with confidence score."""
        text_lower = text.lower()

        scores: dict[EventCategory, float] = {}

        for category, patterns in EVENT_PATTERNS.items():
            matches = 0
            for pat in patterns:
                if re.search(pat, text_lower):
                    matches += 1
            if matches > 0:
                scores[category] = round(min(0.95, 0.65 + 0.15 * matches), 4)

        if not scores:
            return "routine_coverage", 0.60

        top_category = max(scores, key=scores.get)  # type: ignore[arg-type]
        top_confidence = scores[top_category]

        if top_confidence < 0.50:
            return "uncertain", top_confidence

        return top_category, top_confidence
