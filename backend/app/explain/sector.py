"""Evidence-bound Layer 1 stock and industry explanations (Step E3)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    EventItem,
    FundamentalPeriod,
    ModelConfig,
    NewsItem,
    NewsSecurityLink,
    ScoreComponentValue,
    ScoreRun,
    SectorDivergenceRun,
    SectorDivergenceScore,
    SectorMacroSensitivity,
    StockRiskResult,
)
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
from backend.app.explain.sector_math import (
    constituent_period_returns,
    contribution_share,
    peer_median_daily_returns,
    period_return_percent,
    persistence_count,
    rebased_chart_points,
    regression_diagnostics,
    trend_label,
    weak_absolute_percentile,
)
from backend.app.explain.templates import build_sentence
from backend.app.sector_divergence.calculator import ESTIMATION_WINDOW
from backend.app.sector_divergence.inputs import load_inputs

CONFIG_KEY = "explain_sector_rules"
CONFIG_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class DivergenceSubject:
    symbol: str

    @property
    def key(self) -> str:
        return self.symbol.upper()


@dataclass(frozen=True, slots=True)
class SectorSubject:
    industry: str

    @property
    def key(self) -> str:
        return self.industry.strip()


class SectorOverviewItem(BaseModel):
    industry: str
    trend: str
    return_20d: float | None
    breadth: float | None
    dispersion: float | None
    stock_count: int
    flagged_count: int


class SectorOverviewResponse(BaseModel):
    subject: str
    effective_time: date
    method: str
    method_version: str
    input_fingerprint: str
    config_fingerprint: str
    data_age_days: int
    computed_at: datetime
    items: list[SectorOverviewItem]
    limitations: list[str]


def _latest_run(session: Session, as_of: date | None) -> SectorDivergenceRun:
    query = select(SectorDivergenceRun).where(SectorDivergenceRun.status == "completed")
    if as_of is not None:
        query = query.where(SectorDivergenceRun.signal_date <= as_of)
    run = session.scalar(
        query.order_by(
            desc(SectorDivergenceRun.signal_date), desc(SectorDivergenceRun.completed_at)
        ).limit(1)
    )
    if run is None:
        raise LookupError("no completed sector-divergence run is available")
    return run


def _evidence(
    evidence_id: str,
    label: str,
    value: str | int | float | bool | None,
    *,
    run: SectorDivergenceRun,
    source_table: str,
    source_ref: str,
    unit: str | None = None,
    window: str | None = None,
    kind: Literal["statistic", "rule", "event", "config"] = "statistic",
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        label=label,
        value=value,
        unit=unit,
        window=window,
        source_table=source_table,
        source_ref=source_ref,
        as_of=run.signal_date,
        data_age_days=max(0, (date.today() - run.signal_date).days),
    )


def _returns(prices: pd.DataFrame, symbol: str) -> pd.Series:
    return np.log(prices[symbol].astype("float64")).diff()


def _trend_threshold(config: dict[str, Any], horizon: int) -> float:
    thresholds = config.get("trend_thresholds_percent", {})
    if not isinstance(thresholds, dict) or str(horizon) not in thresholds:
        raise ValueError(f"missing trend threshold for {horizon} days")
    return float(thresholds[str(horizon)])


def _scores_for_symbol(
    session: Session, run: SectorDivergenceRun, symbol: str
) -> dict[int, SectorDivergenceScore]:
    rows = session.scalars(
        select(SectorDivergenceScore).where(
            SectorDivergenceScore.run_id == run.id,
            SectorDivergenceScore.symbol == symbol,
        )
    ).all()
    return {row.horizon: row for row in rows}


def _risk_component_evidence(
    session: Session,
    run: SectorDivergenceRun,
    target: SectorDivergenceScore,
    config: dict[str, Any],
) -> list[Evidence]:
    score_run = session.scalar(
        select(ScoreRun)
        .where(
            ScoreRun.status == "completed",
            ScoreRun.as_of_date <= run.signal_date,
            ScoreRun.data_cutoff <= run.data_cutoff,
        )
        .order_by(desc(ScoreRun.as_of_date), desc(ScoreRun.completed_at))
        .limit(1)
    )
    if score_run is None:
        return []
    result = session.scalar(
        select(StockRiskResult).where(
            StockRiskResult.run_id == score_run.id,
            StockRiskResult.security_id == target.security_id,
        )
    )
    component = session.scalar(
        select(ScoreComponentValue).where(
            ScoreComponentValue.run_id == score_run.id,
            ScoreComponentValue.security_id == target.security_id,
            ScoreComponentValue.component_id == "sector_divergence",
        )
    )
    if result is None or component is None or component.points is None:
        return []
    model_config = session.get(ModelConfig, score_run.model_config_id)
    configuration = model_config.configuration if model_config is not None else {}
    weights = configuration.get("component_weights", {}) if configuration else {}
    weight = float(weights.get("sector_divergence", 1.0)) if isinstance(weights, dict) else 1.0
    share = contribution_share(float(component.points), weight, float(result.total_score))
    evidence = [
        _evidence(
            "component_percentile",
            "Sector divergence risk percentile",
            float(component.percentile_rank) if component.percentile_rank is not None else None,
            run=run,
            source_table="score_component_value",
            source_ref=str(component.id),
            unit="percentile",
        ),
        _evidence(
            "component_points",
            "Sector divergence risk points",
            float(component.points),
            run=run,
            source_table="score_component_value",
            source_ref=str(component.id),
            unit="points",
        ),
        _evidence(
            "component_weight",
            "Configured component weight",
            weight,
            run=run,
            source_table="model_config",
            source_ref=str(score_run.model_config_id),
            kind="config",
        ),
        _evidence(
            "total_risk_score",
            "Total risk score",
            float(result.total_score),
            run=run,
            source_table="stock_risk_result",
            source_ref=str(result.id),
            unit="points",
        ),
        _evidence(
            "contribution_share",
            "Configured contribution share",
            round(share, 4) if share is not None else None,
            run=run,
            source_table="score_component_value,model_config,stock_risk_result",
            source_ref=f"{component.id}:{score_run.model_config_id}:{result.id}",
            unit="percent",
        ),
    ]

    risk_rules = config.get("risk_rules", {})
    if not isinstance(risk_rules, dict) or float(target.divergence_value) >= 0:
        return evidence
    rows = session.scalars(
        select(ScoreComponentValue).where(
            ScoreComponentValue.run_id == score_run.id,
            ScoreComponentValue.security_id == target.security_id,
            ScoreComponentValue.percentile_rank.is_not(None),
        )
    ).all()
    fundamental_min = float(risk_rules.get("fundamentals_percentile_min", 75.0))
    volatility_min = float(risk_rules.get("volatility_percentile_min", 75.0))
    support = next(
        (
            row
            for row in rows
            if row.component_id.startswith("fund_")
            and float(row.percentile_rank or 0) >= fundamental_min
        ),
        None,
    )
    label = "elevated fundamental-risk evidence"
    if support is None:
        support = next(
            (
                row
                for row in rows
                if row.component_id == "ewma_volatility"
                and float(row.percentile_rank or 0) >= volatility_min
            ),
            None,
        )
        label = "elevated historical-volatility evidence"
    if support is not None:
        evidence.append(
            _evidence(
                "supporting_signal",
                "Supporting risk evidence",
                label,
                run=run,
                source_table="score_component_value",
                source_ref=str(support.id),
                unit="descriptive reading",
            )
        )
    return evidence


def _coincident_evidence(
    session: Session,
    run: SectorDivergenceRun,
    security_id: object,
    config: dict[str, Any],
) -> list[Evidence]:
    start = run.signal_date - timedelta(days=int(config["event_lookback_days"]))
    events = session.scalars(
        select(EventItem)
        .where(
            EventItem.security_id == security_id,
            EventItem.effective_trading_date.between(start, run.signal_date),
            EventItem.published_at <= run.data_cutoff,
        )
        .order_by(EventItem.effective_trading_date, EventItem.id)
    ).all()
    news = session.execute(
        select(NewsItem, NewsSecurityLink)
        .join(NewsSecurityLink, NewsSecurityLink.news_item_id == NewsItem.id)
        .where(
            NewsSecurityLink.security_id == security_id,
            func.date(NewsItem.published_at).between(start, run.signal_date),
            NewsItem.published_at <= run.data_cutoff,
            NewsItem.ingested_at <= run.data_cutoff,
        )
        .order_by(NewsItem.published_at, NewsItem.id)
    ).all()
    fundamentals = session.scalars(
        select(FundamentalPeriod)
        .where(
            FundamentalPeriod.security_id == security_id,
            func.date(FundamentalPeriod.published_at).between(start, run.signal_date),
            FundamentalPeriod.published_at <= run.data_cutoff,
            FundamentalPeriod.ingested_at <= run.data_cutoff,
        )
        .order_by(FundamentalPeriod.published_at, FundamentalPeriod.id)
    ).all()
    evidence: list[Evidence] = [
        _evidence(
            "coincident_count",
            "Coincident stored publications",
            len(events) + len(news) + len(fundamentals),
            run=run,
            source_table="event_item,news_item,fundamental_period",
            source_ref=f"security:{security_id}:{start}:{run.signal_date}",
            window=f"{start.isoformat()} to {run.signal_date.isoformat()}",
        )
    ]
    markers: list[dict[str, str]] = []
    for index, event_item in enumerate(events):
        marker_id = f"event_{index}"
        evidence.append(
            _evidence(
                marker_id,
                "Company event",
                f"{event_item.effective_trading_date.isoformat()}: {event_item.headline}",
                run=run,
                source_table="event_item",
                source_ref=str(event_item.id),
                kind="event",
            )
        )
        markers.append(
            {
                "date": event_item.effective_trading_date.isoformat(),
                "label": event_item.headline,
            }
        )
    for index, (news_item, _link) in enumerate(news):
        marker_id = f"news_{index}"
        item_date = news_item.published_at.date()
        evidence.append(
            _evidence(
                marker_id,
                "Linked news",
                f"{item_date.isoformat()}: {news_item.headline}",
                run=run,
                source_table="news_item",
                source_ref=str(news_item.id),
                kind="event",
            )
        )
        markers.append({"date": item_date.isoformat(), "label": news_item.headline})
    for index, fundamental_item in enumerate(fundamentals):
        marker_id = f"fundamental_{index}"
        item_date = fundamental_item.published_at.date()
        label = (
            f"{fundamental_item.period_type} fundamentals for "
            f"{fundamental_item.period_end.isoformat()}"
        )
        evidence.append(
            _evidence(
                marker_id,
                "Fundamental publication",
                f"{item_date.isoformat()}: {label}",
                run=run,
                source_table="fundamental_period",
                source_ref=str(fundamental_item.id),
                kind="event",
            )
        )
        markers.append({"date": item_date.isoformat(), "label": label})
    evidence.append(
        _evidence(
            "event_markers",
            "Chart event markers",
            json.dumps(markers, sort_keys=True),
            run=run,
            source_table="event_item,news_item,fundamental_period",
            source_ref=f"security:{security_id}:{start}:{run.signal_date}",
        )
    )
    return evidence


class DivergenceExplainer:
    subject_type = "sector_divergence"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, DivergenceSubject):
            raise TypeError("sector divergence explainer requires DivergenceSubject")
        from backend.app.explain.service import load_explain_config

        config = load_explain_config(session, CONFIG_VERSION, CONFIG_KEY)[0]
        run = _latest_run(session, as_of)
        symbol = subject.symbol.upper()
        scores = _scores_for_symbol(session, run, symbol)
        if set(scores) != {1, 5, 20}:
            raise LookupError(f"{symbol} lacks complete stored 1/5/20-day divergence scores")
        primary = scores[int(config["primary_horizon"])]
        inputs = load_inputs(session, run.signal_date, run.lookback_start, run.data_cutoff)
        if symbol not in inputs.adjusted_closes.columns:
            raise LookupError(f"{symbol} is unavailable in the stored Layer 1 input envelope")
        peers = sorted(
            candidate
            for candidate, industry in inputs.industries.items()
            if industry == primary.industry and candidate != symbol
        )
        minimum_peers = int(config["minimum_contemporaneous_peers"])
        peer_returns = peer_median_daily_returns(inputs.adjusted_closes, peers, minimum_peers)
        stock_returns = _returns(inputs.adjusted_closes, symbol)
        evidence = [
            _evidence(
                "symbol",
                "Symbol",
                symbol,
                run=run,
                source_table="sector_divergence_score",
                source_ref=str(primary.id),
            ),
            _evidence(
                "industry",
                "Official Industry",
                primary.industry,
                run=run,
                source_table="sector_divergence_score",
                source_ref=str(primary.id),
            ),
            _evidence(
                "peer_count",
                "Eligible peer count",
                len(peers),
                run=run,
                source_table="sector_divergence_run",
                source_ref=str(run.id),
            ),
        ]
        windows = [int(value) for value in config["windows"]]
        for horizon in windows:
            sector_value = period_return_percent(peer_returns, horizon)
            stock_value = period_return_percent(stock_returns, horizon)
            if sector_value is not None:
                evidence.extend(
                    [
                        _evidence(
                            f"sector_return_{horizon}",
                            f"Peer median {horizon}-day return",
                            round(sector_value, 4),
                            run=run,
                            source_table="price_daily_adjusted",
                            source_ref=f"{run.id}:{symbol}:peers",
                            unit="percent",
                            window=f"{horizon} trading days",
                        ),
                        _evidence(
                            f"sector_trend_{horizon}",
                            f"Peer median {horizon}-day trend",
                            trend_label(sector_value, _trend_threshold(config, horizon)),
                            run=run,
                            source_table="model_config",
                            source_ref=f"{CONFIG_KEY}:{CONFIG_VERSION}",
                            kind="config",
                        ),
                    ]
                )
            if stock_value is not None:
                evidence.extend(
                    [
                        _evidence(
                            f"stock_return_{horizon}",
                            f"Stock {horizon}-day return",
                            round(stock_value, 4),
                            run=run,
                            source_table="price_daily_adjusted",
                            source_ref=f"{run.id}:{symbol}",
                            unit="percent",
                            window=f"{horizon} trading days",
                        ),
                        _evidence(
                            f"stock_trend_{horizon}",
                            f"Stock {horizon}-day trend",
                            trend_label(stock_value, _trend_threshold(config, horizon)),
                            run=run,
                            source_table="model_config",
                            source_ref=f"{CONFIG_KEY}:{CONFIG_VERSION}",
                            kind="config",
                        ),
                    ]
                )
        peer_20 = constituent_period_returns(inputs.adjusted_closes, peers, 20)
        if peer_20:
            values = list(peer_20.values())
            evidence.extend(
                [
                    _evidence(
                        "breadth",
                        "Peers with positive 20-day return",
                        round(100.0 * sum(value > 0 for value in values) / len(values), 4),
                        run=run,
                        source_table="price_daily_adjusted",
                        source_ref=f"{run.id}:{primary.industry}:breadth",
                        unit="percent",
                        window="20 trading days",
                    ),
                    _evidence(
                        "dispersion",
                        "Peer 20-day return dispersion",
                        round(float(np.std(values, ddof=1)) if len(values) > 1 else 0.0, 4),
                        run=run,
                        source_table="price_daily_adjusted",
                        source_ref=f"{run.id}:{primary.industry}:dispersion",
                        unit="percentage points",
                        window="20 trading days",
                    ),
                ]
            )
        diagnostics = regression_diagnostics(
            stock_returns,
            peer_returns,
            alpha=float(scores[1].alpha),
            beta=float(scores[1].beta),
            estimation_window=ESTIMATION_WINDOW,
        )
        latest_peer = float(peer_returns.iloc[-1])
        evidence.extend(
            [
                _evidence(
                    "alpha",
                    "Stored regression alpha",
                    float(scores[1].alpha),
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=str(scores[1].id),
                    unit="log return",
                ),
                _evidence(
                    "beta",
                    "Stored regression beta",
                    float(scores[1].beta),
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=str(scores[1].id),
                ),
                _evidence(
                    "expected_return",
                    "Regression expected one-day return",
                    round(100.0 * diagnostics.expected_return, 6),
                    run=run,
                    source_table="sector_divergence_score,price_daily_adjusted",
                    source_ref=f"{scores[1].id}:{run.id}",
                    unit="percent",
                    window="1 trading day",
                ),
                _evidence(
                    "residual_1",
                    "One-day regression residual",
                    round(100.0 * diagnostics.residual, 6),
                    run=run,
                    source_table="sector_divergence_score,price_daily_adjusted",
                    source_ref=f"{scores[1].id}:{run.id}",
                    unit="percent",
                    window="1 trading day",
                ),
                _evidence(
                    "r_squared",
                    "Regression R-squared",
                    round(100.0 * diagnostics.r_squared, 4),
                    run=run,
                    source_table="price_daily_adjusted",
                    source_ref=f"{run.id}:{symbol}:regression",
                    unit="percent",
                    window=f"{diagnostics.observations} paired observations",
                ),
                _evidence(
                    "peer_return_1",
                    "Current peer-median log return",
                    latest_peer,
                    run=run,
                    source_table="price_daily_adjusted",
                    source_ref=f"{run.id}:{symbol}:peers",
                    unit="log return",
                    window="1 trading day",
                ),
            ]
        )
        for horizon, score in sorted(scores.items()):
            evidence.extend(
                [
                    _evidence(
                        f"residual_{horizon}_raw",
                        f"Stored {horizon}-day residual",
                        float(score.residual_value),
                        run=run,
                        source_table="sector_divergence_score",
                        source_ref=str(score.id),
                        unit="log return",
                        window=f"{horizon} trading days",
                    ),
                    _evidence(
                        f"z_{horizon}",
                        f"Stored {horizon}-day standardized residual",
                        float(score.divergence_value),
                        run=run,
                        source_table="sector_divergence_score",
                        source_ref=str(score.id),
                        unit="z-score",
                        window=f"{horizon} trading days",
                    ),
                ]
            )
        direction = "outperforming" if float(primary.divergence_value) >= 0 else "underperforming"
        evidence.extend(
            [
                _evidence(
                    "band",
                    "Stored divergence band",
                    primary.interpretation,
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=str(primary.id),
                ),
                _evidence(
                    "direction",
                    "Divergence direction",
                    direction,
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=str(primary.id),
                ),
                _evidence(
                    "risk_rule",
                    "Divergence-alone reading rule",
                    str(config["limitations"][0]),
                    run=run,
                    source_table="model_config",
                    source_ref=f"{CONFIG_KEY}:{CONFIG_VERSION}",
                    kind="rule",
                ),
            ]
        )
        history_rows = session.execute(
            select(SectorDivergenceScore, SectorDivergenceRun)
            .join(SectorDivergenceRun, SectorDivergenceScore.run_id == SectorDivergenceRun.id)
            .where(
                SectorDivergenceScore.symbol == symbol,
                SectorDivergenceScore.horizon == 20,
                SectorDivergenceRun.status == "completed",
                SectorDivergenceRun.signal_date <= run.signal_date,
                SectorDivergenceRun.data_cutoff <= run.data_cutoff,
            )
            .order_by(SectorDivergenceRun.signal_date, SectorDivergenceRun.id)
        ).all()
        history_values = [float(row.divergence_value) for row, _ in history_rows]
        today_peers = session.scalars(
            select(SectorDivergenceScore).where(
                SectorDivergenceScore.run_id == run.id,
                SectorDivergenceScore.horizon == 20,
                SectorDivergenceScore.industry == primary.industry,
            )
        ).all()
        peer_values = [float(row.divergence_value) for row in today_peers]
        evidence.extend(
            [
                _evidence(
                    "history_percentile",
                    "Absolute score percentile in own history",
                    round(
                        weak_absolute_percentile(float(primary.divergence_value), history_values)
                        or 0.0,
                        4,
                    ),
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=f"{symbol}:history-through:{run.id}",
                    unit="percentile",
                ),
                _evidence(
                    "peer_percentile",
                    "Absolute score percentile among today's peers",
                    round(
                        weak_absolute_percentile(float(primary.divergence_value), peer_values)
                        or 0.0,
                        4,
                    ),
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=f"{run.id}:{primary.industry}:absolute",
                    unit="percentile",
                ),
            ]
        )
        persistent, observations = persistence_count(
            history_values, float(config["flag_threshold_abs_z"]), int(config["persistence_window"])
        )
        evidence.extend(
            [
                _evidence(
                    "persistence_count",
                    "Recent dates above absolute threshold",
                    persistent,
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=f"{symbol}:last:{observations}",
                ),
                _evidence(
                    "persistence_observations",
                    "Available recent run dates",
                    observations,
                    run=run,
                    source_table="sector_divergence_score",
                    source_ref=f"{symbol}:last:{observations}",
                ),
            ]
        )
        chart = rebased_chart_points(
            stock_returns.iloc[-61:],
            peer_returns.iloc[-61:],
            max_points=int(config["max_chart_points"]),
        )
        evidence.append(
            _evidence(
                "chart_points",
                "Rebased stock and peer series",
                json.dumps(chart, sort_keys=True),
                run=run,
                source_table="price_daily_adjusted",
                source_ref=f"{run.id}:{symbol}:rebased",
                window="up to 60 trading days",
            )
        )
        evidence.extend(_coincident_evidence(session, run, primary.security_id, config))
        evidence.extend(_risk_component_evidence(session, run, primary, config))
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, DivergenceSubject):
            raise TypeError("sector divergence explainer requires DivergenceSubject")
        by = {item.evidence_id: item for item in evidence}

        def value(key: str) -> str | int | float | bool | None:
            return by[key].value

        templates = config["templates"]
        band_wording = config["band_wording"]
        direction_wording = config["direction_wording"]
        values = {
            "symbol": value("symbol"),
            "industry": value("industry"),
            "direction": value("direction"),
            "sector_return_20": value("sector_return_20"),
            "sector_trend": value("sector_trend_20"),
            "breadth": value("breadth"),
            "dispersion": value("dispersion"),
            "peer_count": value("peer_count"),
            "stock_return_20": value("stock_return_20"),
            "stock_trend": value("stock_trend_20"),
            "expected_return": value("expected_return"),
            "residual_1": value("residual_1"),
            "r_squared": value("r_squared"),
            "z_20": round(float(value("z_20") or 0.0), 3),
            "band_text": band_wording[str(value("band"))],
            "direction_text": direction_wording[str(value("direction"))],
            "history_percentile": value("history_percentile"),
            "peer_percentile": value("peer_percentile"),
            "persistence_count": value("persistence_count"),
            "persistence_observations": value("persistence_observations"),
            "coincident_count": value("coincident_count"),
        }
        if "supporting_signal" in by:
            values["supporting_signal"] = value("supporting_signal")
        if "component_points" in by:
            values.update(
                {
                    "component_percentile": value("component_percentile"),
                    "component_points": value("component_points"),
                    "component_weight": value("component_weight"),
                    "contribution_share": value("contribution_share"),
                }
            )

        def sentence(name: str, ids: list[str]) -> ExplanationSentence | None:
            return build_sentence(str(templates[name]), values, ids, config)

        not_verdict = sentence("divergence_not_verdict", ["risk_rule"])
        flagged = sentence("flagged", ["z_20", "band", "direction"])
        summary = [item for item in [flagged, not_verdict] if item is not None]
        chart = {
            "type": "stock_sector_rebased",
            "indexed_to": 100,
            "points": json.loads(str(value("chart_points"))),
            "event_markers": json.loads(str(value("event_markers"))),
            "residual_shaded": True,
        }
        sections = [
            ExplanationSection(
                key="sector_trend",
                title="Sector trend",
                sentences=[
                    item
                    for item in [
                        sentence(
                            "sector_trend", ["sector_return_20", "sector_trend_20", "breadth"]
                        ),
                        sentence("sector_dispersion", ["dispersion", "peer_count"]),
                    ]
                    if item
                ],
                chart_spec=chart,
            ),
            ExplanationSection(
                key="stock_trend",
                title="Stock trend",
                sentences=[
                    item
                    for item in [sentence("stock_trend", ["stock_return_20", "stock_trend_20"])]
                    if item
                ],
            ),
            ExplanationSection(
                key="why_flagged",
                title="Why flagged",
                sentences=[
                    item
                    for item in [
                        sentence(
                            "expected",
                            ["alpha", "beta", "expected_return", "residual_1", "r_squared"],
                        ),
                        flagged,
                        sentence("unusual", ["history_percentile", "peer_percentile"]),
                        sentence("persistence", ["persistence_count", "persistence_observations"]),
                        sentence("coincident", ["coincident_count"]),
                    ]
                    if item
                ],
            ),
            ExplanationSection(
                key="risk_reading",
                title="Is it risky?",
                sentences=[
                    item
                    for item in [
                        not_verdict,
                        sentence("risk_supported", ["z_20", "supporting_signal"]),
                    ]
                    if item
                ],
            ),
            ExplanationSection(
                key="contribution",
                title="How much it matters",
                sentences=[
                    item
                    for item in [
                        sentence(
                            "contribution",
                            [
                                "component_percentile",
                                "component_points",
                                "component_weight",
                                "total_risk_score",
                                "contribution_share",
                            ],
                        )
                    ]
                    if item
                ],
            ),
        ]
        limitations: list[str] = []
        if int(value("persistence_observations") or 0) < int(config["persistence_window"]):
            limitations.append("Persistence uses fewer than the configured 20 available run dates.")
        if "component_points" not in by:
            limitations.append(
                "No point-in-time stock risk run was available for contribution evidence."
            )
        if "supporting_signal" not in by:
            limitations.append(
                "No configured supporting fundamental or volatility evidence met the "
                "risk-reading threshold."
            )
        as_of = evidence[0].as_of
        return ExplanationPayload(
            headline=str(templates["stock_headline"]).format(
                symbol=value("symbol"), direction=value("direction"), industry=value("industry")
            ),
            summary_points=summary,
            sections=sections,
            evidence=evidence,
            limitations=limitations,
            confidence=ExplanationConfidence(
                level="high" if "component_points" in by else "medium",
                reasons=[
                    ExplanationSentence(
                        text=(
                            "Stored 1, 5 and 20-day Layer 1 results and their "
                            "point-in-time price inputs are available."
                        ),
                        evidence_ids=["z_1", "z_5", "z_20", "peer_count"],
                    )
                ],
            ),
            data_age=ExplanationDataAge(
                days=evidence[0].data_age_days,
                as_of=as_of,
                status="fresh" if (evidence[0].data_age_days or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type=self.subject_type, key=subject.key),
            disclaimer="",
            effective_time=as_of,
            method="Leave-one-out peer median, trailing OLS and standardized residual",
            method_version="sector-divergence-v1",
            lookback={"estimation_trading_days": 60, "divergence_horizons": [1, 5, 20]},
            units={"returns": "percent", "divergence": "z-score", "risk": "points"},
            thresholds={
                "trend_percent": config["trend_thresholds_percent"],
                "flag_abs_z": config["flag_threshold_abs_z"],
            },
            component_contributions=[]
            if "component_points" not in by
            else [
                {
                    "component_id": "sector_divergence",
                    "points": value("component_points"),
                    "weight": value("component_weight"),
                    "share_percent": value("contribution_share"),
                }
            ],
            data_sufficiency="complete" if "component_points" in by else "partial",
            computed_at=datetime.now(UTC),
        )


class SectorExplainer:
    subject_type = "sector"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, SectorSubject):
            raise TypeError("sector explainer requires SectorSubject")
        from backend.app.explain.service import load_explain_config

        config = load_explain_config(session, CONFIG_VERSION, CONFIG_KEY)[0]
        run = _latest_run(session, as_of)
        inputs = load_inputs(session, run.signal_date, run.lookback_start, run.data_cutoff)
        symbols = sorted(
            symbol for symbol, industry in inputs.industries.items() if industry == subject.industry
        )
        if not symbols:
            raise LookupError(
                f"industry '{subject.industry}' is absent from the stored Layer 1 run"
            )
        sector_returns = peer_median_daily_returns(
            inputs.adjusted_closes, symbols, int(config["minimum_contemporaneous_peers"])
        )
        sector_20 = period_return_percent(sector_returns, 20)
        constituent_20 = constituent_period_returns(inputs.adjusted_closes, symbols, 20)
        values = list(constituent_20.values())
        scores = session.scalars(
            select(SectorDivergenceScore).where(
                SectorDivergenceScore.run_id == run.id,
                SectorDivergenceScore.industry == subject.industry,
                SectorDivergenceScore.horizon == 20,
            )
        ).all()
        threshold = float(config["flag_threshold_abs_z"])
        evidence = [
            _evidence(
                "industry",
                "Official Industry",
                subject.industry,
                run=run,
                source_table="sector_divergence_score",
                source_ref=f"{run.id}:{subject.industry}",
            ),
            _evidence(
                "stock_count",
                "Scored industry stocks",
                len(scores),
                run=run,
                source_table="sector_divergence_score",
                source_ref=f"{run.id}:{subject.industry}",
            ),
            _evidence(
                "flagged_count",
                "Flagged industry stocks",
                sum(abs(float(row.divergence_value)) >= threshold for row in scores),
                run=run,
                source_table="sector_divergence_score",
                source_ref=f"{run.id}:{subject.industry}:flagged",
            ),
            _evidence(
                "flag_threshold",
                "Configured absolute flag threshold",
                threshold,
                run=run,
                source_table="model_config",
                source_ref=f"{CONFIG_KEY}:{CONFIG_VERSION}",
                kind="config",
            ),
            _evidence(
                "sector_return_20",
                "Industry median 20-day return",
                round(sector_20, 4) if sector_20 is not None else None,
                run=run,
                source_table="price_daily_adjusted",
                source_ref=f"{run.id}:{subject.industry}:median",
                unit="percent",
                window="20 trading days",
            ),
            _evidence(
                "sector_trend",
                "Industry 20-day trend",
                trend_label(sector_20, _trend_threshold(config, 20))
                if sector_20 is not None
                else None,
                run=run,
                source_table="model_config",
                source_ref=f"{CONFIG_KEY}:{CONFIG_VERSION}",
                kind="config",
            ),
            _evidence(
                "breadth",
                "Positive 20-day breadth",
                round(100.0 * sum(item > 0 for item in values) / len(values), 4)
                if values
                else None,
                run=run,
                source_table="price_daily_adjusted",
                source_ref=f"{run.id}:{subject.industry}:breadth",
                unit="percent",
            ),
            _evidence(
                "dispersion",
                "20-day return dispersion",
                round(float(np.std(values, ddof=1)), 4) if len(values) > 1 else 0.0,
                run=run,
                source_table="price_daily_adjusted",
                source_ref=f"{run.id}:{subject.industry}:dispersion",
                unit="percentage points",
            ),
            _evidence(
                "top_divergers",
                "Largest absolute divergences",
                ", ".join(
                    f"{row.symbol} {float(row.divergence_value):+.2f}"
                    for row in sorted(
                        scores, key=lambda item: (-abs(float(item.divergence_value)), item.symbol)
                    )[:5]
                ),
                run=run,
                source_table="sector_divergence_score",
                source_ref=f"{run.id}:{subject.industry}:top",
            ),
        ]
        macro = session.scalars(
            select(SectorMacroSensitivity)
            .where(
                SectorMacroSensitivity.industry == subject.industry,
                SectorMacroSensitivity.window_end <= run.signal_date,
                SectorMacroSensitivity.is_significant.is_(True),
            )
            .order_by(
                desc(SectorMacroSensitivity.window_end),
                desc(func.abs(SectorMacroSensitivity.t_stat)),
            )
            .limit(3)
        ).all()
        if macro:
            evidence.append(
                _evidence(
                    "macro_drivers",
                    "Significant macro sensitivities",
                    ", ".join(f"{row.series_key} beta {row.beta:+.2f}" for row in macro),
                    run=run,
                    source_table="sector_macro_sensitivity",
                    source_ref=":".join(str(row.id) for row in macro),
                )
            )
        security_ids = [inputs.security_ids[symbol] for symbol in symbols]
        start = run.signal_date - timedelta(days=int(config["event_lookback_days"]))
        event_count = (
            session.scalar(
                select(func.count(EventItem.id)).where(
                    EventItem.security_id.in_(security_ids),
                    EventItem.effective_trading_date.between(start, run.signal_date),
                    EventItem.published_at <= run.data_cutoff,
                )
            )
            or 0
        )
        news_count = (
            session.scalar(
                select(func.count(NewsSecurityLink.id))
                .join(NewsItem, NewsItem.id == NewsSecurityLink.news_item_id)
                .where(
                    NewsSecurityLink.security_id.in_(security_ids),
                    func.date(NewsItem.published_at).between(start, run.signal_date),
                    NewsItem.published_at <= run.data_cutoff,
                    NewsItem.ingested_at <= run.data_cutoff,
                )
            )
            or 0
        )
        evidence.append(
            _evidence(
                "news_count",
                "Industry-linked stored news and events",
                int(event_count + news_count),
                run=run,
                source_table="event_item,news_item",
                source_ref=f"{run.id}:{subject.industry}:{start}",
            )
        )
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, SectorSubject):
            raise TypeError("sector explainer requires SectorSubject")
        by = {item.evidence_id: item for item in evidence}
        values: dict[str, object] = {key: item.value for key, item in by.items()}
        templates = config["templates"]

        def sentence(name: str, ids: list[str]) -> ExplanationSentence | None:
            return build_sentence(str(templates[name]), values, ids, config)

        sections = [
            ExplanationSection(
                key="sector_trend",
                title="Sector trend",
                sentences=[
                    item
                    for item in [
                        sentence(
                            "sector_overview",
                            ["sector_return_20", "sector_trend", "breadth", "dispersion"],
                        )
                    ]
                    if item
                ],
            ),
            ExplanationSection(
                key="flagged",
                title="Flagged stocks",
                sentences=[
                    item
                    for item in [
                        sentence(
                            "sector_flagged", ["flagged_count", "stock_count", "flag_threshold"]
                        ),
                        sentence("sector_divergers", ["top_divergers"]),
                    ]
                    if item
                ],
            ),
            ExplanationSection(
                key="macro",
                title="Macro sensitivities",
                sentences=[item for item in [sentence("sector_macro", ["macro_drivers"])] if item],
            ),
            ExplanationSection(
                key="news",
                title="News pressure",
                sentences=[item for item in [sentence("sector_news", ["news_count"])] if item],
            ),
        ]
        limitations = (
            []
            if "macro_drivers" in by
            else [
                "No significant stored macro sensitivity was available for this industry and date."
            ]
        )
        as_of = evidence[0].as_of
        return ExplanationPayload(
            headline=str(templates["sector_headline"]).format(industry=subject.industry),
            summary_points=[
                item
                for item in [
                    sentence(
                        "sector_overview",
                        ["sector_return_20", "sector_trend", "breadth", "dispersion"],
                    )
                ]
                if item
            ],
            sections=sections,
            evidence=evidence,
            limitations=limitations,
            confidence=ExplanationConfidence(
                level="high",
                reasons=[
                    ExplanationSentence(
                        text=(
                            "The explanation uses the complete stored industry peer set "
                            "for the selected Layer 1 run."
                        ),
                        evidence_ids=["industry", "stock_count"],
                    )
                ],
            ),
            data_age=ExplanationDataAge(
                days=evidence[0].data_age_days,
                as_of=as_of,
                status="fresh" if (evidence[0].data_age_days or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type=self.subject_type, key=subject.key),
            disclaimer="",
            effective_time=as_of,
            method="Industry median returns and stored sector-divergence-v1 outputs",
            method_version="sector-divergence-v1",
            lookback={"trend_trading_days": 20},
            units={"return": "percent", "divergence": "z-score"},
            thresholds={
                "trend_percent": config["trend_thresholds_percent"],
                "flag_abs_z": config["flag_threshold_abs_z"],
            },
            data_sufficiency="complete",
            computed_at=datetime.now(UTC),
        )


def build_sector_overview(session: Session, as_of: date | None = None) -> SectorOverviewResponse:
    from backend.app.explain.service import load_explain_config

    config, _, fingerprint = load_explain_config(session, CONFIG_VERSION, CONFIG_KEY)
    run = _latest_run(session, as_of)
    inputs = load_inputs(session, run.signal_date, run.lookback_start, run.data_cutoff)
    scores = session.scalars(
        select(SectorDivergenceScore).where(
            SectorDivergenceScore.run_id == run.id, SectorDivergenceScore.horizon == 20
        )
    ).all()
    by_industry: dict[str, list[SectorDivergenceScore]] = {}
    for score in scores:
        by_industry.setdefault(score.industry, []).append(score)
    items: list[SectorOverviewItem] = []
    for industry in sorted(set(inputs.industries.values())):
        symbols = sorted(symbol for symbol, value in inputs.industries.items() if value == industry)
        returns = peer_median_daily_returns(
            inputs.adjusted_closes, symbols, int(config["minimum_contemporaneous_peers"])
        )
        return_20 = period_return_percent(returns, 20)
        constituent = list(constituent_period_returns(inputs.adjusted_closes, symbols, 20).values())
        industry_scores = by_industry.get(industry, [])
        items.append(
            SectorOverviewItem(
                industry=industry,
                trend=trend_label(return_20, _trend_threshold(config, 20))
                if return_20 is not None
                else "unavailable",
                return_20d=round(return_20, 4) if return_20 is not None else None,
                breadth=round(100.0 * sum(value > 0 for value in constituent) / len(constituent), 4)
                if constituent
                else None,
                dispersion=round(float(np.std(constituent, ddof=1)), 4)
                if len(constituent) > 1
                else (0.0 if constituent else None),
                stock_count=len(industry_scores),
                flagged_count=sum(
                    abs(float(row.divergence_value)) >= float(config["flag_threshold_abs_z"])
                    for row in industry_scores
                ),
            )
        )
    return SectorOverviewResponse(
        subject="sectors:NIFTY_200",
        effective_time=run.signal_date,
        method="Industry median returns and stored sector-divergence-v1 outputs",
        method_version="sector-divergence-v1",
        input_fingerprint=run.input_fingerprint,
        config_fingerprint=fingerprint,
        data_age_days=max(0, (date.today() - run.signal_date).days),
        computed_at=run.completed_at or run.started_at,
        items=items,
        limitations=[
            "Industries are the official stored Industry values, not a separate sector taxonomy.",
            "Daily adjusted closing prices are not real-time prices.",
        ],
    )


registry.register(DivergenceExplainer())
registry.register(SectorExplainer())
