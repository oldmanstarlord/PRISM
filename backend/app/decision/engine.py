"""PRISM Stock Decision Engine — core scoring and classification.

Integration architecture:
    1.  FundamentalAdapter  → reads StockMetricDaily.score (five-factor risk score,
                              cross-sectional percentile, 0–100 where higher = MORE risk).
                              Inverted to Fundamental Strength Score: 100 − risk_score.
                              Supplemented by anomaly_isolation_forest predictions.

    2.  SectorDivergenceAdapter → reads SectorDivergenceScore.industry_percentile from the
                                  latest completed sector divergence run (horizon 20 days).
                                  industry_percentile is already a 0–100 rank; higher = better.
                                  Uses existing backend.app.sector_divergence.service module.

    3.  NewsScoreAdapter → delegates to existing NewsIntelligenceService, extracts
                           per-symbol mean_sentiment_score in [-1, 1] and maps it to
                           [0, 100]:  news_score = (mean_sentiment_score + 1.0) / 2.0 * 100
                           Confidence-gated: defaults to 50 (neutral) when unavailable.

    4.  DynamicWeighter → selects weight regime based on news event materiality.

    5.  StockDecisionEngine → combines scores, applies thresholds, generates explanations.

No ML model is retrained. No sector divergence algorithm is duplicated.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ModelPrediction,
    ModelRun,
    SectorDivergenceScore,
    StockMetricDaily,
)
from backend.app.decision.schemas import (
    AppliedWeights,
    ConfidenceLevel,
    DecisionFlag,
    FundamentalScorePayload,
    NewsScorePayload,
    PortfolioDecisionResponse,
    PortfolioDecisionSummary,
    SectorStrengthPayload,
    StockDecision,
)
from backend.app.market_data.metrics import METHODOLOGY_VERSION
from backend.app.sector_divergence.service import latest_completed_run_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decision thresholds (per spec — initial assumptions, not backtested)
# ---------------------------------------------------------------------------
HOLD_THRESHOLD = 70.0  # >= HOLD
WATCH_THRESHOLD = 45.0  # >= WAIT & WATCH, < HOLD
# < WATCH_THRESHOLD -> SELL

# ---------------------------------------------------------------------------
# Default weight regimes
# ---------------------------------------------------------------------------
WEIGHTS_NORMAL: dict[str, float] = {
    "fundamental": 0.60,
    "sector": 0.25,
    "news": 0.15,
}
WEIGHTS_SIGNIFICANT_NEWS: dict[str, float] = {
    "fundamental": 0.55,
    "sector": 0.20,
    "news": 0.25,
}
WEIGHTS_CRITICAL_EVENT: dict[str, float] = {
    "fundamental": 0.50,
    "sector": 0.15,
    "news": 0.35,
}

# Critical event categories that trigger enhanced news weight
CRITICAL_EVENT_CATEGORIES = {"litigation", "regulation", "m&a"}
SIGNIFICANT_EVENT_CATEGORIES = {"earnings", "guidance"} | CRITICAL_EVENT_CATEGORIES

# High-confidence threshold for news; below this we fall back to neutral
NEWS_CONFIDENCE_THRESHOLD = 0.55

# Anomaly isolation forest: the explanation dict carries is_anomaly_ml
ANOMALY_MODEL_NAME = "anomaly_isolation_forest"


# ---------------------------------------------------------------------------
# 1. Fundamental Adapter
# ---------------------------------------------------------------------------


def _fetch_fundamental_score(session: Session, symbol: str) -> FundamentalScorePayload:
    """Read the persisted five-factor risk score from StockMetricDaily.

    The five-factor risk score is a cross-sectional percentile score where
    HIGHER = MORE RISK (0 = safest, 100 = riskiest).  We invert it to produce
    a Fundamental Strength Score so that the decision engine can uniformly
    treat higher scores as better across all three components.

    Transformation: fundamental_strength = 100.0 − five_factor_risk_score
    """
    try:
        latest_date = session.scalar(
            select(func.max(StockMetricDaily.metric_date)).where(
                StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
                StockMetricDaily.symbol == symbol,
            )
        )
        if latest_date is None:
            return FundamentalScorePayload(
                symbol=symbol,
                fundamental_strength_score=50.0,
                fundamental_classification="Unknown",
                availability="unavailable",
                failure_reason="no_metric_date_for_symbol",
            )
        row = session.scalar(
            select(StockMetricDaily).where(
                StockMetricDaily.symbol == symbol,
                StockMetricDaily.metric_date == latest_date,
                StockMetricDaily.methodology_version == METHODOLOGY_VERSION,
            )
        )
        if row is None or row.score is None:
            return FundamentalScorePayload(
                symbol=symbol,
                fundamental_strength_score=50.0,
                fundamental_classification="Unknown",
                availability="unavailable",
                failure_reason="metric_row_missing_or_score_null",
            )
        if row.quality_status == "fail":
            return FundamentalScorePayload(
                symbol=symbol,
                fundamental_strength_score=50.0,
                fundamental_classification="Unknown",
                raw_risk_score=float(row.score),
                quality_status=row.quality_status,
                availability="unavailable",
                failure_reason="quality_status_fail",
            )

        risk_score = float(row.score)
        strength_score = round(100.0 - risk_score, 2)

        if strength_score >= 75:
            classification = "Strong"
        elif strength_score >= 55:
            classification = "Moderate"
        elif strength_score >= 35:
            classification = "Weak"
        else:
            classification = "Very Weak"

        # Check for anomaly signal from ML model
        anomaly_flag = False
        anomaly_score_val: float | None = None
        anomaly_model_version: str | None = None
        try:
            anomaly_run: ModelRun | None = session.scalar(
                select(ModelRun)
                .where(
                    ModelRun.model_name == ANOMALY_MODEL_NAME,
                    ModelRun.status.in_({"ready", "baseline_selected"}),
                )
                .order_by(desc(ModelRun.trained_at))
                .limit(1)
            )
            if anomaly_run is not None:
                anomaly_model_version = anomaly_run.model_version
                pred: ModelPrediction | None = session.scalar(
                    select(ModelPrediction)
                    .where(
                        ModelPrediction.run_id == anomaly_run.id,
                        ModelPrediction.target_type == "anomaly_score",
                        ModelPrediction.symbol == symbol,
                    )
                    .order_by(desc(ModelPrediction.prediction_date))
                    .limit(1)
                )
                if pred is not None and pred.explanation:
                    details = dict(pred.explanation)
                    anomaly_flag = bool(details.get("is_anomaly_ml", False))
                    if pred.predicted_value is not None:
                        anomaly_score_val = float(pred.predicted_value)
        except Exception as exc:
            logger.debug("Could not retrieve anomaly signal for %s: %s", symbol, exc)

        return FundamentalScorePayload(
            symbol=symbol,
            fundamental_strength_score=strength_score,
            fundamental_classification=classification,
            raw_risk_score=risk_score,
            anomaly_flag=anomaly_flag,
            anomaly_score=anomaly_score_val,
            model_source="five_factor_risk_score_inverted",
            model_version=anomaly_model_version or METHODOLOGY_VERSION,
            data_cutoff=row.metric_date,
            quality_status=row.quality_status,
            availability="available",
        )
    except Exception as exc:
        logger.warning("Fundamental adapter failed for %s: %s", symbol, exc)
        return FundamentalScorePayload(
            symbol=symbol,
            fundamental_strength_score=50.0,
            fundamental_classification="Unknown",
            availability="unavailable",
            failure_reason=str(exc)[:200],
        )


# ---------------------------------------------------------------------------
# 2. Sector Divergence Adapter
# ---------------------------------------------------------------------------


def _fetch_sector_strength(
    session: Session,
    symbol: str,
    run_id: Any,
) -> SectorStrengthPayload:
    """Read the industry_percentile from the latest completed sector divergence run.

    The industry_percentile is a rank-based 0–100 score where:
    - 100 = the stock had the highest divergence (outperformer) in its sector
    - 0   = the lowest (underperformer)

    This is already a validated, distribution-relative normalization —
    no clamping or ad-hoc scaling is applied.
    Horizon 20 days is used (consistent with stock_risk.py).
    """
    try:
        if run_id is None:
            return SectorStrengthPayload(
                symbol=symbol,
                sector_strength_score=50.0,
                availability="no_run",
                failure_reason="no_completed_sector_divergence_run",
            )
        row: SectorDivergenceScore | None = session.scalar(
            select(SectorDivergenceScore).where(
                SectorDivergenceScore.run_id == run_id,
                SectorDivergenceScore.symbol == symbol,
                SectorDivergenceScore.horizon == 20,
            )
        )
        if row is None:
            return SectorStrengthPayload(
                symbol=symbol,
                sector_strength_score=50.0,
                availability="unavailable",
                failure_reason="symbol_not_in_sector_divergence_run",
            )
        return SectorStrengthPayload(
            symbol=symbol,
            sector=row.industry,
            divergence_value=round(float(row.divergence_value), 4),
            sector_strength_score=round(float(row.industry_percentile), 2),
            interpretation=row.interpretation,
            horizon_days=20,
            source="existing_sector_divergence_module",
            availability="available",
        )
    except Exception as exc:
        logger.warning("Sector divergence adapter failed for %s: %s", symbol, exc)
        return SectorStrengthPayload(
            symbol=symbol,
            sector_strength_score=50.0,
            availability="unavailable",
            failure_reason=str(exc)[:200],
        )


# ---------------------------------------------------------------------------
# 3. News Sentiment Adapter
# ---------------------------------------------------------------------------


def _fetch_news_score(
    holdings: list[dict[str, Any]],
) -> dict[str, NewsScorePayload]:
    """Delegate to the existing NewsIntelligenceService.

    Returns a per-symbol dict of NewsScorePayload.

    Transformation:
        mean_sentiment_score ∈ [-1.0, 1.0]
        news_score = (mean_sentiment_score + 1.0) / 2.0 × 100
        → maps -1 → 0,  0 → 50,  +1 → 100

    Confidence gate: if sentiment confidence is below threshold, or no articles
    were found, we default to 50 (neutral) and mark is_fallback_neutral=True.

    This prevents fabricating a positive/negative signal from noise.
    """
    results: dict[str, NewsScorePayload] = {}
    try:
        from backend.app.news.service import NewsIntelligenceService

        svc = NewsIntelligenceService(use_transformer=False)  # lexicon for speed
        intel = svc.get_portfolio_news_intelligence(holdings=holdings)

        for summary in intel.holding_summaries:
            sym = summary.symbol.upper()
            score = summary.mean_sentiment_score
            n_articles = summary.article_count_7d

            # True confidence from the sentiment analyzer output is not available
            # per-holding in the summary; use article count as a confidence proxy.
            # With < 2 articles, confidence is low regardless of score.
            confidence_est = min(1.0, n_articles / 5.0) if n_articles > 0 else 0.0

            is_fallback = confidence_est < 0.20 or n_articles == 0

            if is_fallback:
                news_score = 50.0
                sentiment_label = "neutral"
            else:
                news_score = round((score + 1.0) / 2.0 * 100.0, 2)
                news_score = max(0.0, min(100.0, news_score))
                sentiment_label = summary.dominant_sentiment

            results[sym] = NewsScorePayload(
                symbol=sym,
                news_score=news_score,
                sentiment=sentiment_label,
                news_confidence=round(confidence_est, 4),
                articles_analyzed=n_articles,
                major_events=[str(e) for e in summary.primary_event_categories],
                provider_status=intel.provider_status,
                is_fallback_neutral=is_fallback,
            )
    except Exception as exc:
        logger.warning("News sentiment adapter failed: %s", exc)
        # Return empty dict; caller handles missing symbols with neutral fallback
    return results


def _neutral_news_payload(
    symbol: str, reason: str = "news_service_unavailable"
) -> NewsScorePayload:
    return NewsScorePayload(
        symbol=symbol,
        news_score=50.0,
        sentiment="neutral",
        news_confidence=0.0,
        articles_analyzed=0,
        provider_status="not_configured",
        is_fallback_neutral=True,
        failure_reason=reason,
    )


# ---------------------------------------------------------------------------
# 4. Dynamic Weight Selection
# ---------------------------------------------------------------------------


def _select_weights(
    news_payload: NewsScorePayload,
    news_articles: int,
) -> AppliedWeights:
    """Apply dynamic weight regime based on news materiality and reliability.

    Rules:
    - Fundamental weight is always the highest.
    - Enhanced news weight requires: sufficient articles, reasonable confidence,
      and a significant/critical event category.
    - Weights always sum to 1.0.
    """
    # Event categories detected
    critical_events = {e for e in news_payload.major_events if e in CRITICAL_EVENT_CATEGORIES}
    significant_events = {e for e in news_payload.major_events if e in SIGNIFICANT_EVENT_CATEGORIES}

    has_sufficient_data = news_articles >= 3 and news_payload.news_confidence >= 0.35
    has_critical = bool(critical_events) and has_sufficient_data
    has_significant = bool(significant_events) and has_sufficient_data

    if has_critical:
        w = WEIGHTS_CRITICAL_EVENT
        regime = "critical_event"
        reason = f"Critical events detected: {', '.join(sorted(critical_events))}"
    elif has_significant:
        w = WEIGHTS_SIGNIFICANT_NEWS
        regime = "significant_news"
        reason = f"Significant events detected: {', '.join(sorted(significant_events))}"
    else:
        w = WEIGHTS_NORMAL
        regime = "normal"
        reason = "No material credible events detected; default weights applied"

    return AppliedWeights(
        fundamental=w["fundamental"],
        sector=w["sector"],
        news=w["news"],
        regime=regime,
        regime_reason=reason,
    )


# ---------------------------------------------------------------------------
# 5. Score Calculation and Decision Classification
# ---------------------------------------------------------------------------


def _calculate_final_score(
    fundamental_score: float,
    sector_score: float,
    news_score: float,
    weights: AppliedWeights,
) -> float:
    score = (
        weights.fundamental * fundamental_score
        + weights.sector * sector_score
        + weights.news * news_score
    )
    return round(max(0.0, min(100.0, score)), 2)


def _classify_decision(
    final_score: float,
    fundamental: FundamentalScorePayload,
    sector: SectorStrengthPayload,
    news: NewsScorePayload,
    weights: AppliedWeights,
) -> tuple[DecisionFlag, ConfidenceLevel, str, list[str], list[str]]:
    """Apply decision thresholds and override rules.

    Returns: (decision, confidence, explanation, reasons, risk_alerts)
    """
    reasons: list[str] = []
    risk_alerts: list[str] = []

    # --- Score-based base decision ---
    if final_score >= HOLD_THRESHOLD:
        base_decision: DecisionFlag = "HOLD"
    elif final_score >= WATCH_THRESHOLD:
        base_decision = "WAIT & WATCH"
    else:
        base_decision = "SELL"

    decision = base_decision

    # --- Reason generation ---
    fs = fundamental.fundamental_strength_score
    ss = sector.sector_strength_score
    ns = news.news_score

    if fs >= 70:
        reasons.append(
            f"Strong fundamental health signal ({fs:.0f}/100 strength; "
            f"cross-sectional risk score = {fundamental.raw_risk_score:.1f}/100)."
        )
    elif fs >= 50:
        reasons.append(f"Moderate fundamental health signal ({fs:.0f}/100 strength).")
    else:
        reasons.append(
            f"Weak fundamental health signal ({fs:.0f}/100 strength; "
            f"risk score = {fundamental.raw_risk_score:.1f}/100 — elevated cross-sectional risk)."
        )

    if sector.availability == "available":
        if ss >= 65:
            reasons.append(
                f"Stock is outperforming its sector peers "
                f"(industry percentile {ss:.0f}/100, divergence={sector.divergence_value:+.2f}σ)."
            )
        elif ss >= 35:
            reasons.append(
                f"In-line with sector peers "
                f"(industry percentile {ss:.0f}/100, divergence={sector.divergence_value:+.2f}σ)."
            )
        else:
            reasons.append(
                f"Underperforming sector peers "
                f"(industry percentile {ss:.0f}/100, divergence={sector.divergence_value:+.2f}σ)."
            )
    else:
        reasons.append("Sector divergence data unavailable; defaulting to neutral sector score.")

    if news.is_fallback_neutral:
        reasons.append(
            f"Insufficient news data ({news.articles_analyzed} articles). "
            "News score defaulted to neutral (50/100)."
        )
    elif ns >= 65:
        reasons.append(
            f"Recent news sentiment is positive ({ns:.0f}/100, "
            f"sentiment={news.sentiment}, articles={news.articles_analyzed})."
        )
    elif ns >= 40:
        reasons.append(
            f"Recent news sentiment is neutral ({ns:.0f}/100, articles={news.articles_analyzed})."
        )
    else:
        reasons.append(
            f"Recent news sentiment is negative ({ns:.0f}/100, "
            f"sentiment={news.sentiment}, articles={news.articles_analyzed})."
        )

    # --- Risk override alerts (do NOT change the score-based decision alone) ---
    if fundamental.anomaly_flag:
        risk_alerts.append(
            "ANOMALY DETECTED: The isolation-forest ML model flagged unusual price behaviour. "
            "Monitor closely for unexplained volatility or data errors."
        )

    if sector.availability == "available" and sector.divergence_value is not None:
        if sector.divergence_value <= -3.0:
            risk_alerts.append(
                f"EXTREME SECTOR UNDERPERFORMANCE: Divergence z-score of "
                f"{sector.divergence_value:+.2f}σ is in the extreme range."
            )

    critical_events = [e for e in news.major_events if e in CRITICAL_EVENT_CATEGORIES]
    if critical_events:
        risk_alerts.append(
            f"CRITICAL EVENT CATEGORIES DETECTED in recent news: "
            f"{', '.join(critical_events)}. Review primary sources before any action."
        )

    # --- Boundary conditions: escalate borderline decisions when risk signals are stacked ---
    if decision == "HOLD" and fundamental.anomaly_flag and fs < 60:
        decision = "WAIT & WATCH"
        reasons.append(
            "Decision escalated to WAIT & WATCH: anomaly flag combined with weaker "
            "fundamental strength."
        )

    if decision == "HOLD" and len(risk_alerts) >= 2:
        decision = "WAIT & WATCH"
        reasons.append("Decision escalated to WAIT & WATCH due to multiple concurrent risk alerts.")

    # --- Confidence assessment ---
    data_sources_available = sum(
        [
            fundamental.availability == "available",
            sector.availability == "available",
            not news.is_fallback_neutral,
        ]
    )
    if data_sources_available == 3:
        confidence: ConfidenceLevel = "high"
    elif data_sources_available == 2:
        confidence = "medium"
    elif data_sources_available == 1:
        confidence = "low"
    else:
        confidence = "insufficient_data"

    # Near-boundary dampens confidence
    if abs(final_score - HOLD_THRESHOLD) < 5 or abs(final_score - WATCH_THRESHOLD) < 5:
        if confidence == "high":
            confidence = "medium"
        elif confidence == "medium":
            confidence = "low"

    # --- Narrative explanation ---
    explanation = (
        f"{fundamental.symbol}: Final Health Score = {final_score:.1f}/100 → {decision}. "
        f"Fundamental Strength = {fs:.0f}/100 (×{(weights.fundamental * 100):.0f}% weight), "
        f"Sector Strength = {ss:.0f}/100 (×{(weights.sector * 100):.0f}% weight), "
        f"News Score = {ns:.0f}/100 (×{(weights.news * 100):.0f}% weight). "
        f"Confidence: {confidence}. Weight regime: {weights.regime}."
    )

    return decision, confidence, explanation, reasons, risk_alerts


# ---------------------------------------------------------------------------
# 6. Portfolio-level analysis orchestrator
# ---------------------------------------------------------------------------


def analyze_portfolio_decisions(
    holdings: list[dict[str, Any]],
    session: Session,
) -> PortfolioDecisionResponse:
    """Analyze all portfolio holdings and assign SELL / HOLD / WAIT & WATCH flags.

    Args:
        holdings: List of holding dicts with keys: symbol, companyName/company_name,
                  sector, quantity, buyPrice/buy_price, weight.
        session:  Active SQLAlchemy session (required for DB adapters).

    Returns:
        PortfolioDecisionResponse with per-stock decisions and portfolio summary.
    """
    now_iso = datetime.now(UTC).isoformat()

    # Normalize holding keys for downstream compatibility
    normalized_holdings: list[dict[str, Any]] = []
    for h in holdings:
        nh = {
            "symbol": str(h.get("symbol", "")).upper(),
            "companyName": h.get("company_name") or h.get("companyName"),
            "sector": h.get("sector"),
            "quantity": float(h.get("quantity", 1.0)),
            "buyPrice": float(h.get("buy_price") or h.get("buyPrice") or 1.0),
            "weight": float(h.get("weight") or 0.0),
        }
        normalized_holdings.append(nh)

    # Resolve latest sector divergence run ID once (avoid N+1 queries)
    latest_run = session.scalar(latest_completed_run_query())
    run_id = latest_run.id if latest_run else None

    # Fetch news intelligence for all holdings at once (single feed pass)
    try:
        news_scores_by_symbol = _fetch_news_score(normalized_holdings)
    except Exception as exc:
        logger.warning("News service call failed for portfolio: %s", exc)
        news_scores_by_symbol = {}

    decisions: list[StockDecision] = []

    for nh in normalized_holdings:
        sym = nh["symbol"]
        if not sym:
            continue

        # — Fundamental —
        fundamental = _fetch_fundamental_score(session, sym)

        # — Sector divergence —
        sector = _fetch_sector_strength(session, sym, run_id)

        # — News —
        news = news_scores_by_symbol.get(sym) or _neutral_news_payload(
            sym, "symbol_not_in_news_response"
        )

        # If all three sources are unavailable, mark as unanalyzable
        all_unavailable = (
            fundamental.availability == "unavailable"
            and sector.availability in {"unavailable", "no_run"}
            and news.is_fallback_neutral
        )
        if all_unavailable and fundamental.failure_reason == "no_metric_date_for_symbol":
            decisions.append(
                StockDecision(
                    symbol=sym,
                    company_name=nh.get("companyName"),
                    sector=nh.get("sector"),
                    fundamental=fundamental,
                    sector_strength=sector,
                    news=news,
                    applied_weights=AppliedWeights(
                        fundamental=0.60,
                        sector=0.25,
                        news=0.15,
                        regime="normal",
                        regime_reason="not_computed",
                    ),
                    final_score=50.0,
                    decision="WAIT & WATCH",
                    confidence="insufficient_data",
                    explanation=f"{sym}: Insufficient data to produce a reliable decision.",
                    reasons=["No persisted metric data found for this symbol."],
                    risk_alerts=[],
                    analysis_timestamp=now_iso,
                    data_freshness="unavailable",
                    status="unavailable",
                    status_reason=fundamental.failure_reason,
                )
            )
            continue

        # — Dynamic weights —
        weights = _select_weights(news, news.articles_analyzed)

        # Use 50 for unavailable components (neutral fallback)
        fs = fundamental.fundamental_strength_score
        ss = sector.sector_strength_score
        ns = news.news_score

        final_score = _calculate_final_score(fs, ss, ns, weights)

        decision_flag, confidence, explanation, reasons, risk_alerts = _classify_decision(
            final_score, fundamental, sector, news, weights
        )

        decisions.append(
            StockDecision(
                symbol=sym,
                company_name=nh.get("companyName"),
                sector=sector.sector or nh.get("sector"),
                fundamental=fundamental,
                sector_strength=sector,
                news=news,
                applied_weights=weights,
                final_score=final_score,
                decision=decision_flag,
                confidence=confidence,
                explanation=explanation,
                reasons=reasons,
                risk_alerts=risk_alerts,
                analysis_timestamp=now_iso,
                data_freshness=(
                    str(fundamental.data_cutoff) if fundamental.data_cutoff else "unknown"
                ),
            )
        )

    # Portfolio summary
    hold_count = sum(1 for d in decisions if d.decision == "HOLD" and d.status == "analyzed")
    watch_count = sum(
        1 for d in decisions if d.decision == "WAIT & WATCH" and d.status == "analyzed"
    )
    sell_count = sum(1 for d in decisions if d.decision == "SELL" and d.status == "analyzed")
    unavail_count = sum(1 for d in decisions if d.status == "unavailable")

    # Portfolio-weighted risk exposure: % of portfolio weight flagged SELL
    total_weight = sum(float(nh.get("weight") or 0.0) for nh in normalized_holdings)
    sell_symbols = {d.symbol for d in decisions if d.decision == "SELL" and d.status == "analyzed"}
    sell_weight = sum(
        float(nh.get("weight") or 0.0) for nh in normalized_holdings if nh["symbol"] in sell_symbols
    )
    weighted_risk = round((sell_weight / total_weight * 100.0) if total_weight > 0 else 0.0, 2)

    analyzed = [d for d in decisions if d.status == "analyzed"]
    avg_score = round(sum(d.final_score for d in analyzed) / len(analyzed), 2) if analyzed else None

    summary = PortfolioDecisionSummary(
        total_stocks=len(decisions),
        hold_count=hold_count,
        wait_and_watch_count=watch_count,
        sell_count=sell_count,
        unavailable_count=unavail_count,
        portfolio_weighted_risk_exposure=weighted_risk,
        average_final_score=avg_score,
        analysis_timestamp=now_iso,
    )

    return PortfolioDecisionResponse(
        summary=summary,
        decisions=decisions,
    )
