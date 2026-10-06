# PRISM Explanation Specification: Design, Guardrails & Defense

**Document ID:** `docs/specs/EXPLANATION_SPEC.md`  
**Phase:** Step E6 — Explanation Faithfulness, Safety Guardrails & Language Governance  
**Authority:** `PRISM_SRS.md` Sections 10, 14, 16; `docs/agent/MASTER_CONTEXT.md` Rules D1, D3, D8, D9, D10, D11.

---

## 1. Architectural Architecture & Design Principles

PRISM explanations transform multidimensional quantitative risk outputs into clear, readable, and mathematically faithful narratives. The explanation engine is built on four core design invariants:

1. **Rule D8 — Evidence-Bound Invariant:** Every sentence presented to a user is produced from an immutable template filled exclusively with explicit evidence items extracted from stored database records. Every sentence carries an `evidence_ids` array citing its source data. Sentences lacking verified evidence are dropped.
2. **Rule D9 — Non-Causal & No Advice Invariant:** Statistical relationships are described as co-movement ("moves together with"), never causation ("because of", "caused by"). Future price forecasts and investment recommendations (`buy`, `sell`, `hold`, `target price`) are banned by automated CI guards.
3. **Rule D1 — Config-Driven:** Templates, wording bands, and thresholds are stored in versioned `model_config` rows with cryptographic checksums (`configuration_hash`).
4. **Rule D3 — Result Envelope:** Every explanation response is enclosed in an envelope containing subject metadata, effective timestamp, method version, input fingerprint, lookback window, units, data age, confidence reasons, limitations, and regulatory disclaimers.

---

## 2. Evidence Architecture & Kinds

An evidence item represents an atomic, verifiable unit of quantitative or configuration context.

```python
class Evidence(BaseModel):
    evidence_id: str
    kind: Literal["statistic", "rule", "event", "config"]
    label: str
    value: str | int | float | bool | None
    unit: str | None = None
    window: str | None = None
    source_table: str
    source_ref: str
    as_of: date
    data_age_days: int | None = None
```

### Evidence Kinds
1. **`statistic`**: Empirical observations computed without look-ahead (e.g. 30-day EWMA volatility, OLS beta, Kruskal tree edge rank, ENB entropy). Source tables: `stock_risk_result`, `score_component_value`, `mst_edge`, `portfolio_diversification_result`.
2. **`rule`**: Versioned qualitative classification or state assigned by the scoring engine (e.g. divergence status `divergent`, alert status `active`, transmission path description).
3. **`event`**: Timestamped external record ingested into PRISM (e.g. company announcement, corporate action, SEBI circular). Source tables: `event_item`, `news_item`.
4. **`config`**: Quantitative parameter, weight, or threshold active for that specific score run (e.g. component weight $w_k$, minimum peer count, stability threshold). Source table: `model_config`.

---

## 3. Template Engine & Sentence Composition

PRISM avoids runtime text generation. Instead, templates use Python formatting placeholders filled only when every required placeholder exists in the evidence dictionary:

```python
def build_sentence(
    template: str,
    values: dict[str, object],
    evidence_ids: list[str],
    config: dict[str, object],
) -> ExplanationSentence | None:
    if not evidence_ids:
        return None
    fields = [name for _, name, _, _ in Formatter().parse(template) if name]
    if any(field not in values or values[field] is None for field in fields):
        return None
    text = template.format(**values)
    validate_text(text, config)
    return ExplanationSentence(text=text, evidence_ids=evidence_ids)
```

If any variable in `{variable}` is missing or unsupported by stored data, `build_sentence` returns `None`. The resulting section either renders only supported sentences or is omitted entirely with a limitation notice.

---

## 4. Deterministic Guardrails & CI Enforcement

All generated explanation text, templates, and glossary definitions pass through automated safety guards before reaching the API or frontend:

### 4.1 Banned Investment Advice Phrases
The following phrases trigger an immediate `ValueError` in code and fail CI builds:
- `buy`, `sell`, `hold`
- `target price`, `price target`
- `guaranteed`, `risk-free`, `certain profit`
- `will rise`, `will fall`
- `you should invest`

### 4.2 Forbidden Causal Wording
Economic and statistical associations must never be framed as direct physical or economic causes:
- Banned: `because of`, `caused by`, `will cause`, `led to`
- Permitted: `moves together with`, `historical co-movement`, `possible transmission path`, `scenario response`

### 4.3 Mandatory Correlation Phrasing
Any occurrence of `correlation` or `correlated` must be explicitly qualified by `moves together with` within the same sentence or explanatory block.

---

## 5. System Limitations & Boundaries

1. **Scenario Boundaries:** Shock simulations represent linear stress tests on historical covariance matrices; they do not simulate order-book liquidity exhaustion or dynamic margin liquidation spirals.
2. **End-of-Day Data Cutoff:** Prices and volume inputs reflect official exchange daily closing prices, not real-time intraday tick data.
3. **Sparse Graph Approximation:** Minimum Spanning Trees retain exactly $N-1$ edges out of $N(N-1)/2$ possible pairwise correlations. Omission of an edge in the MST does not imply that two stocks are uncorrelated.
4. **Review Status:** Regulatory policy rules and draft templates seeded during migration retain `UNREVIEWED_SEED` status until approved by the system owner.

---

## 6. Viva Defense: Questions & Answers

### Q1: Why use fixed deterministic templates instead of a Large Language Model (LLM)?
**Defense:**
1. **Zero Hallucination Guarantee:** Financial risk management cannot tolerate fabricated statistics. Fixed templates guarantee that every numeric value displayed to the user originated directly from verified database rows.
2. **Complete Auditability:** In regulatory environments (SEBI, RBI, SEC), every user-facing claim must be reproducible. A hash of the template plus stored evidence yields an identical explanation byte-for-byte.
3. **Point-in-Time Compliance (Rule D4):** LLMs contain training look-ahead bias and unpredictable latent associations. Templates operate strictly on records with `published_at <= as_of`.
4. **Latency & Cost:** Evaluating an LLM takes 1,000–3,000 ms per query and incurs recurring API costs. PRISM's in-memory template interpolation executes in under **10 milliseconds**, enabling real-time dashboard rendering.

### Q2: Why must every explanation sentence be evidence-bound?
**Defense:**
Rule D8 mandates that no statement exists without an explicit link to one or more primary-key-backed evidence records. If market data for a component is missing or corrupted, the sentence is omitted rather than approximated. This ensures mathematical faithfulness: the explanation never claims an asset has low volatility unless the EWMA calculation record exists, is within the data age threshold, and matches the reported score points.

### Q3: Why is there a strict prohibition on investment advice and causal statements?
**Defense:**
1. **Regulatory Mandate:** Under the SEBI (Investment Advisers) Regulations, 2013, providing personalized recommendations (`buy`, `sell`, `target price`) requires formal licensing and fiduciary suitability analysis. PRISM is an empirical risk intelligence tool, not an advisory service.
2. **Epistemological Integrity:** In financial econometrics, empirical correlation does not imply causality. Two assets may move together due to unobserved latent macro factors or coincident liquidity flows. Presenting correlation as causation misleads risk managers during regime shifts.

### Q4: How does the explanation engine maintain performance across thousands of stocks and network edges?
**Defense:**
PRISM employs a dual-tier caching and precomputation strategy:
1. **Deterministic Fingerprinting:** Input data and config parameters are hashed into a 64-character SHA-256 fingerprint. If inputs have not changed, cached explanations are fetched from the database in ~420ms (well under the 1.0s budget).
2. **Batch Precomputation:** The nightly batch job `jobs/precompute_explanations.py` builds explanations for the top $N$ risk assets, all active MST edges, moderate-or-higher sector divergences, and recent news impacts.
3. **On-Demand Fallback:** For low-traffic assets, pure in-memory compose runs in <50ms and end-to-end database-backed generation takes <1.5s (under the 3.0s budget).
