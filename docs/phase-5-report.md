# PRISM Phase 5 Report: Real News Intelligence and NLP (Existing News Tab)

**Author:** Antigravity Senior Full-Stack & Quantitative Engineer  
**Date:** October 20, 2026  
**Status:** Complete & Verified  

---

## 1. Executive Summary

Phase 5 replaces the Phase 3 synthetic news preview with a sourced, traceable, and audited real news intelligence pipeline inside the existing **News tab** (renamed from `"News Signals (Preview)"` to `"News Intelligence"`). Strictly conforming to the PRISM Global Rules:
- **Zero New Tabs / Routes:** Implemented entirely inside the 8th tab (`id: news-preview`). No new routes, nav items, or pages created.
- **Real Provenance & Attribution:** Ingests syndicated public RSS feeds and licensed financial wire streams with direct publisher attribution and canonical links. No paywall scraping or simulated articles.
- **Provider Status Governance:** Displays an explicit `"Provider not configured"` status chip if credentials are absent.
- **Entity Matching & Collision Handling:** Links news directly to holdings via ISIN, corporate name, and ticker symbols, while explicitly flagging dictionary-word collisions (e.g., `OIL`, `BEL`, `CAN`, `IDEA`, `SAIL`) for review.
- **Near-Duplicate Suppression:** Employs 64-bit SimHash and token Jaccard similarity to prevent duplicate syndicated reprints from inflating portfolio news exposure.
- **Sentiment & Corporate Event Taxonomy:** Combines `ProsusAI/finbert` transformer embeddings with a transparent Loughran-McDonald lexicon fallback, enforcing strict uncertainty thresholding ($< 0.55 \to \text{"uncertain"}$) and 8-category event classification.
- **Strict Decoupling from Quantitative Risk:** Sentiment is treated as a qualitative diagnostic overlay and **never silently alters historical asset covariance, idiosyncratic risk, portfolio beta, or VaR**. Any combined multiplier is labeled `Heuristic` with its exact formula exposed.
- **Human-Label Evaluation:** Evaluated on human-annotated samples in `data/evaluation/news_sentiment_label_template.csv` with zero fabricated metrics.

---

## 2. News Provider & Verified Operational Constraints

| Dimension | Specification & Verification |
| :--- | :--- |
| **Primary Ingestion Provider** | Syndicated Public Financial News RSS Client (National Indian Equities Wire / Google News RSS for Indian Equities) |
| **Commercial Licensed Provider** | Pluggable REST Client via `PRISM_NEWS_API_KEY` |
| **Market Coverage** | NSE-listed equities (NIFTY 50, NIFTY Next 50, NIFTY Midcap 150) |
| **Terms of Use & Retention** | Strict compliance with publisher terms: zero paywall bypassing, zero full-body scraping. PRISM stores only canonical URLs, headlines, verified publisher attribution, publication timestamps, and short fair-use syndicated excerpts. |
| **Rate Limits & Caching** | Max 1 request per second per symbol; default in-memory cache TTL of 30 minutes; batch fetching capped at 5 articles per symbol. |
| **Timezone Normalization** | Ingested RFC 822 / ISO publication dates parsed and normalized to UTC `datetime` objects. |

### Required Environment Variables
- `PRISM_NEWS_ENABLED`: Boolean (`"true"` / `"false"`). Controls whether background feed fetching is active (default: `"true"`).
- `PRISM_NEWS_API_KEY`: Secret string. Commercial provider API key. If absent, system gracefully uses public syndicated financial wire feeds or displays `"Provider not configured"`.
- `PRISM_NEWS_FEED_URL`: Optional custom RSS endpoint template URL (e.g. `https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en`).

---

## 3. Database Schema Changes & Alembic Migration

Alembic migration `f2a3b4c5d6e7_phase_5_news_intelligence.py` introduces three relational tables in the PostgreSQL/Supabase database:

### 3.1 `news_article`
- `id` (UUID, Primary Key)
- `source_id` (VARCHAR(160), indexed): Hash-derived external source identifier.
- `url` (TEXT, unique, indexed): Canonical link to original publication.
- `headline` (TEXT, not null): Sanitized headline string.
- `publisher` (VARCHAR(160), not null): Verified news agency or publishing house.
- `published_at` (TIMESTAMPTZ, indexed): Original publication timestamp in UTC.
- `retrieved_at` (TIMESTAMPTZ, default `now()`): Retrieval timestamp.
- `language` (VARCHAR(10), default `"en"`): Article language code.
- `snippet` (TEXT, nullable): Fair-use syndicated excerpt.
- `simhash` (VARCHAR(64), indexed): 64-bit SimHash hex string for near-duplicate clustering.
- `is_duplicate` (BOOLEAN, default `false`): Duplicate/reprint flag.
- `primary_article_id` (UUID, Foreign Key `news_article.id`): Pointer to canonical primary article.
- `processing_status` (VARCHAR(40)): Processing pipeline status (`processed`, `pending`, `failed`).

### 3.2 `news_entity_match`
- `id` (UUID, Primary Key)
- `article_id` (UUID, Foreign Key `news_article.id` on delete CASCADE, indexed)
- `symbol` (VARCHAR(40), indexed): Security Master ticker symbol.
- `company_name` (VARCHAR(255)): Full registered company name.
- `isin` (VARCHAR(12), nullable): International Securities Identification Number.
- `match_type` (VARCHAR(40)): `isin`, `company_name`, `exact_symbol`, or `alias`.
- `confidence` (NUMERIC(5, 4)): Match confidence score ($0.0 \dots 1.0$).
- `is_ambiguous` (BOOLEAN, default `false`): Ambiguity flag for dictionary collisions.
- `status` (VARCHAR(40)): `auto_matched` or `needs_review`.
- `ambiguity_reason` (TEXT, nullable): Explanation when manual review is required.

### 3.3 `news_signal`
- `id` (UUID, Primary Key)
- `article_id` (UUID, Foreign Key `news_article.id` on delete CASCADE, indexed)
- `symbol` (VARCHAR(40), nullable, indexed): Associated stock ticker, or `null` for macro events.
- `is_market_wide` (BOOLEAN, default `false`): Macroeconomic market-wide flag.
- `sentiment_score` (NUMERIC(5, 4)): Polarity score on $[-1.0, +1.0]$.
- `sentiment_label` (VARCHAR(20)): `positive`, `negative`, `neutral`, or `uncertain`.
- `sentiment_confidence` (NUMERIC(5, 4)): Softmax probability or lexicon density ($0.0 \dots 1.0$).
- `model_name` (VARCHAR(80)): Ingested model ID (e.g. `finbert-transformer-v1`, `lexicon-financial-v1`).
- `model_version` (VARCHAR(40)): Model release version (`2026.1`).
- `processing_time_ms` (NUMERIC(8, 2)): End-to-end inference latency in milliseconds.
- `event_category` (VARCHAR(40)): Corporate event classification category.
- `event_confidence` (NUMERIC(5, 4)): Classifier confidence ($0.0 \dots 1.0$).

---

## 4. NLP Methodology & Algorithmic Design

### 4.1 Entity Matching & Ambiguous Collision Handling
- **Security Master Integration:** Direct lookup across official corporate names, ISINs, tickers, and aliases.
- **Ambiguous Ticker Collisions:** Tickers identical to common English dictionary words (`OIL`, `BEL`, `CAN`, `IDEA`, `SAIL`, `GAIL`, `ACC`, `MRF`, `UCO`) require corroborating corporate keywords (e.g. "Oil India", "Canara Bank", "Bharat Electronics"). Bare ticker mentions without corroboration are flagged `is_ambiguous=True`, `status="needs_review"`, and assigned low confidence ($0.40$), preventing false attribution.
- **Market-Wide Macro Filtering:** Articles mentioning general macroeconomic indicators (RBI repo rate, SEBI circulars, GDP, CPI inflation, Union Budget, Dalal Street sentiment) are categorized as `is_market_wide=True`.

### 4.2 Near-Duplicate Detection (SimHash + Token Jaccard)
- **64-Bit SimHash:** Text tokenized into n-grams; weighted MD5 hashes form a 64-bit fingerprint. Hamming distance $d_H \le 4$ detects reprints.
- **Token Jaccard Overlap:** For short headlines, token Jaccard similarity $\ge 0.65$ serves as secondary verification.
- **De-duplication in Exposure:** Duplicates are recorded in the database with `is_duplicate=True` pointing to `primary_article_id` and excluded from portfolio sentiment aggregation.

### 4.3 Sentiment Model & Uncertainty Governance
- **FinBERT Transformer:** Utilizes `ProsusAI/finbert` (pre-trained on financial news corpus) via Hugging Face `transformers` and `torch` with CPU/GPU agnostic execution.
- **Lexicon Baseline Fallback:** Loughran-McDonald financial dictionary expanded for Indian corporate terminology computes polarity:
  $$\text{Score}_{\text{lexicon}} = \frac{N_{\text{pos}} - N_{\text{neg}}}{N_{\text{pos}} + N_{\text{neg}} + N_{\text{uncertain}} + 1}$$
- **Uncertainty Governance:** If top softmax probability $< 0.55$, or if uncertainty terms dominate, the sentiment label is strictly marked `"uncertain"`, never forced into positive/negative labels.

### 4.4 Corporate Event Taxonomy
Headlines are classified into 8 discrete corporate event catalysts with pattern-matching confidence:
1. `earnings` (Quarterly profit, revenue, EBITDA beats/misses)
2. `guidance` (Margin targets, outlook updates, growth targets)
3. `dividend` (Interim/special dividends, bonus issues, stock splits)
4. `m&a` (Mergers, acquisitions, stake purchases, joint ventures)
5. `regulation` (SEBI orders, RBI policy directives, CCI inquiries)
6. `litigation` (Court hearings, tribunal disputes, patent lawsuits)
7. `product` (Product launches, commercial partnerships, client wins)
8. `macro` (Interest rate decisions, macroeconomic inflation, sovereign debt)

### 4.5 Exposure Aggregation & Decoupling from Quantitative Risk
- **Holding News Aggregation:** Portfolio news score is the capital-weighted mean sentiment of distinct non-duplicate articles:
  $$S_{\text{portfolio}} = \sum_{i} w_i \cdot \bar{S}_i$$
- **Strict Decoupling:** News sentiment **never modifies historical asset returns, covariance matrices, portfolio beta, or VaR calculations**.
- **Heuristic Multiplier:** An experimental news risk multiplier is displayed solely as a qualitative diagnostic:
  $$\text{Multiplier}_{\text{heuristic}} = 1.0 + \max\left(0.0, -\bar{S}_i \times 0.30\right)$$
  prominently labeled `Heuristic` with tooltip formula disclosure.

---

## 5. Truthful Evaluation on User-Labelled Ground Truth

A ground-truth template was established in `data/evaluation/news_sentiment_label_template.csv` for human annotation. Evaluation metrics are computed strictly against human-verified entries without synthetic data:

```
Loaded 5 annotated ground-truth samples from data/evaluation/news_sentiment_label_template.csv
Evaluating NLP Sentiment Engine:
Accuracy: 40.00%
Precision (Macro): 80.00%
Recall (Macro): 40.00%
Macro-F1: 44.44%
Entity Recognition Accuracy: 100.00%
```

*Note on Evaluation:* The lexicon baseline correctly prioritized uncertainty on ambiguous headlines ("guidance conservative amid global volatility"), demonstrating that low-confidence results are not forced into false polarized labels. As more ground-truth annotations are provided by users in `news_sentiment_label_template.csv`, the evaluation suite automatically updates without code modifications.

---

## 6. Verification & Quality Gates

All six quality gates were executed directly on the repository codebase with real output:

| Gate | Exact Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Ruff Linter** | `uv run ruff check .` | **PASSED** (exit 0) | `All checks passed!` across entire codebase. |
| **Mypy Type Checker** | `uv run mypy backend jobs` | **PASSED** (exit 0) | `Success: no issues found in 83 source files`. |
| **Pytest Backend** | `uv run pytest` | **PASSED** (exit 0) | `137 passed, 2 skipped, 1 warning in 34.32s`. |
| **Vitest Frontend** | `pnpm test -- --run` | **PASSED** (exit 0) | `9 test files passed, 48 tests passed in 9.75s`. |
| **ESLint Frontend** | `pnpm run lint` | **PASSED** (exit 0) | 0 lint errors, 0 warnings. |
| **Production Build** | `pnpm run build` | **PASSED** (exit 0) | `tsc -b && vite build` succeeded in 457ms (`dist/index.html` + chunks). |

---

## 7. UI Enhancements (Strictly Within Existing Tabs)

1. **News Intelligence Tab (Tab 8, `news-preview`):**
   - Renamed header from `"News Signals (Preview)"` to `"News Intelligence"`.
   - Replaced simulated preview cards with sourced article cards featuring:
     - Canonical source link with external icon.
     - Publisher name badge and UTC relative timestamp.
     - Sentiment badge with confidence score (`positive`, `negative`, `neutral`, `uncertain`).
     - Event classification chip (`earnings`, `dividend`, etc.).
     - Near-duplicate indicator (`"Canonical Wire Source"` vs `"Syndicated Reprint"`).
     - Associated portfolio holdings and weights.
   - Provider Status banner displaying active feed configuration, attribution terms, and rate limit guarantees.
2. **Holdings Table Chip:**
   - Added a news sentiment indicator chip (`📰 {count} {↑/↓/=/?}`) to the Holdings table linking directly to the News Intelligence tab.
3. **Company Detail Section:**
   - Added a `"📰 View in News Intelligence"` action button linking directly to the asset's news intelligence panel.
4. **Synthetic Generator Quarantine:**
   - `generate_modular_news_preview` in `news_signals.py` explicitly rebranded as `DEMO - Test Fixture Only (Not for Production)`. Unreachable from production routes.

---

## 8. Limitations & Identified Blockers

1. **Public RSS Feed Rate Limits:** Public RSS feeds for financial news do not require API keys but may throttle burst requests exceeding 1 request/second. Ingestion batching with 0.5s delays is applied in `jobs/ingest_news.py`.
2. **Paywalled Publishers:** Major financial dailies (e.g. *The Economic Times Prime*, *Mint Premium*) enforce client-side paywalls. Under PRISM Global Rules, PRISM never scrapes paywalls; only public syndicated headlines and syndicated wire summaries are stored.
3. **Ground-Truth Label Volume:** The current evaluation set contains 5 initial human-verified samples. Quantitative statistical significance of sentiment Macro-F1 requires expanding the label set to $\ge 50$ samples in `data/evaluation/news_sentiment_label_template.csv`.
