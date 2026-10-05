# PRISM Policy Risk Specification (POLICY_SPEC)

**Dimension:** `macro` (Weight: 5.0% in PRISM Risk Score, configurable per D1)  
**Component ID:** `news_policy_pressure`  
**Method Version:** `news-policy-pressure-v1`  
**Status:** DRAFT / Specification (Pending User Sign-off)  

---

## 1. Official Regulatory Feeds & Storage Contract (SRS FR-D9, OQ-7)

PRISM strictly tracks official regulatory and government policy announcements impacting Indian capital markets.

### Approved Primary Sources
1. **Reserve Bank of India (RBI)**: Official Press Releases (`https://rbi.org.in/pressreleases_rss.xml`). Terms: Public domain official communication; informational fair-use.
2. **Securities and Exchange Board of India (SEBI)**: Public Regulatory Press Releases (`https://www.sebi.gov.in/sebirss.xml`). Terms: Official statutory regulator notices; public fair-use.

The previously configured PIB URL returned HTTP 403 during verification on 2026-10-06 and is disabled. No replacement URL is guessed; a verified official PIB feed remains TBD.

### Strict Content Storage & Copyright Guardrails
Per PRISM design requirements and fair-use boundaries:
- **Stored Fields**: `headline`, `url`, `source`, `published_at`, `ingested_at`, `content_hash` (SHA-256 of `headline + source + published_at`).
- **Forbidden**: Full article text, editorial commentary, or redistributed vendor body text is strictly prohibited from storage and transmission.
- **Deduplication**: Ingestion jobs enforce uniqueness on `content_hash`. Repetitive polling produces zero duplicates and executes idempotently.

---

## 2. Deterministic Transmission Rules & Audit Governance

Policy transmission into industry risk pressure operates via deterministic keyword and category matching. **No rule may exist without a written economic rationale.**

### Rule Schema (`policy_rule`)
- `rule_key` (VARCHAR 64, Unique): Immutable canonical key.
- `version` (INT): Incremental version number.
- `description` (TEXT): High-level operational summary.
- `match_keywords` (JSONB): List of lowercase string tokens matched against the headline.
- `match_category` (VARCHAR 64): High-level policy sector (`monetary`, `banking`, `capital_markets`, `taxation`, `trade`, `infrastructure`).
- `affected_industries` (JSONB): Array of 18 Layer 1 canonical industries affected by the transmission channel.
- `direction` (VARCHAR 16): `headwind` (increases risk pressure), `tailwind` (mitigates risk pressure), or `ambiguous` (neutral/contextual).
- `severity` (NUMERIC 3, 1): Severity rating on $[1.0, 10.0]$ scale.
- `rationale` (TEXT, NOT NULL): Detailed economic transmission mechanism explaining *why* and *how* the policy impacts operating margin, credit conditions, or capital costs.
- `reviewer` (VARCHAR 64, NOT NULL): Human reviewer identifier responsible for approving or editing the rule.
- `active` (BOOLEAN): Soft-disable switch.

### Versioning Protocol
Rules are immutable once reviewed. Any update via `PUT /policy/rules/{key}` creates a new active version row, increments the version counter, requires a non-empty reviewer and rationale, and archives previous versions.

---

## 3. Mathematical Formulation of `news_policy_pressure`

The `news_policy_pressure` component computes recency-decayed headwind pressure for a given stock's industry over a lookback window of $L = 60$ days.

### Recency Decay
For each matched policy event $i$ occurring at trading date $t_i \le t$ with age $\Delta t_i = t - t_i$ days:
$$w_i = 2^{-\Delta t_i / \lambda}$$
where $\lambda = 14$ days (half-life parameter seeded in `model_config`).

### Gross Headwind Pressure
$$\text{GrossHeadwind} = \sum_{i \in \text{Headwinds}} \text{severity}_i \times 2^{-\Delta t_i / 14}$$

### Tailwind Mitigation Cap
Positive policy tailwinds reduce overall pressure, but cannot erase fundamental downside risk. Tailwind mitigation is capped at a strict 30% of gross headwind pressure:
$$\text{GrossTailwind} = \sum_{j \in \text{Tailwinds}} \text{severity}_j \times 2^{-\Delta t_j / 14}$$
$$\text{Mitigation} = \min\left(\text{GrossTailwind}, 0.30 \times \text{GrossHeadwind}\right)$$
$$\text{NetPressure} = \max\left(0.0, \text{GrossHeadwind} - \text{Mitigation}\right)$$

### Normalization to Component Score $S_{\text{policy}} \in [0, 100]$
Using standard scaling parameter $K_{\text{scale}} = 20.0$:
$$S_{\text{policy}} = \min\left(100.0, \max\left(0.0, \frac{\text{NetPressure}}{K_{\text{scale}}} \times 100.0\right)\right)$$

If an industry has zero matched policy events within the lookback window:
$$S_{\text{policy}} = 0.0, \quad \text{data\_sufficiency} = \text{"sufficient"}$$

---

## 4. Seeded Draft Policy Rules (8–10 Initial Rules)

Ten foundational policy rules are seeded as `status = DRAFT` for domain review:

1. **`rbi_repo_rate_hike`** (`monetary`):
   - Keywords: `repo rate hike`, `policy repo rate increased`, `tightening monetary stance`
   - Industries: `Banks`, `Financial Services`, `Automobile and Auto Components`, `Realty`
   - Direction: `headwind`, Severity: 7.5
   - Rationale: Higher borrowing costs compress interest coverage, elevate retail lending delinquencies, and dampen capital expenditure and real estate demand.
2. **`rbi_repo_rate_cut`** (`monetary`):
   - Keywords: `repo rate cut`, `reduction in repo rate`, `policy rate eased`
   - Industries: `Banks`, `Financial Services`, `Automobile and Auto Components`, `Realty`
   - Direction: `tailwind`, Severity: 6.5
   - Rationale: Monetary easing lowers wholesale funding costs, improves borrowing appetite, and stimulates interest-sensitive consumption and capex.
3. **`rbi_unsecured_risk_weights`** (`banking`):
   - Keywords: `risk weights on unsecured`, `consumer credit risk weight`, `higher provisioning unsecured`
   - Industries: `Banks`, `Financial Services`
   - Direction: `headwind`, Severity: 8.0
   - Rationale: Mandatory capital buffer increases for unsecured personal loans and credit cards restrain loan book growth and compress Tier-1 capital adequacy.
4. **`windfall_tax_crude_increase`** (`taxation`):
   - Keywords: `special additional excise duty crude`, `windfall tax on crude raised`, `export duty petroleum increased`
   - Industries: `Oil Gas & Consumable Fuels`
   - Direction: `headwind`, Severity: 7.0
   - Rationale: Additional duties on domestically extracted crude and refined fuels reduce net realized refining margins (GRMs) and cash generation.
5. **`fdi_limit_defense_liberalized`** (`trade`):
   - Keywords: `fdi limit defense`, `defense production indigenisation`, `make in india defense allocation`
   - Industries: `Capital Goods`
   - Direction: `tailwind`, Severity: 6.0
   - Rationale: Expansion of FDI limits and domestic capital procurement carve-outs boost multi-year order books for defense manufacturing.
6. **`pli_incentive_pharma_expansion`** (`infrastructure`):
   - Keywords: `production linked incentive pharma`, `pli scheme api ksm`, `bulk drug parks incentive`
   - Industries: `Healthcare`
   - Direction: `tailwind`, Severity: 5.5
   - Rationale: Government capital subsidies and revenue incentives reduce raw material dependence on imports and expand operating margins.
7. **`export_duty_steel_hike`** (`trade`):
   - Keywords: `export duty on steel`, `iron ore pellets duty increased`, `curb steel exports`
   - Industries: `Metals & Mining`
   - Direction: `headwind`, Severity: 7.5
   - Rationale: Tariffs on outgoing metallurgical exports constrain domestic producers' price realization and force surplus supply into the local market.
8. **`it_h1b_visa_curbs`** (`trade`):
   - Keywords: `h-1b visa fee increase`, `cross-border tech wage rules`, `offshore tech tax`
   - Industries: `Information Technology`
   - Direction: `headwind`, Severity: 6.5
   - Rationale: Regulatory impediments to on-site mobility and rising visa filing expenses inflate service delivery overhead for tier-1 IT exporters.
9. **`power_tariff_subsidy_rationalization`** (`infrastructure`):
   - Keywords: `discom late payment surcharge`, `revamped distribution sector scheme`, `smart metering mandate`
   - Industries: `Power`
   - Direction: `tailwind`, Severity: 6.0
   - Rationale: Enforcement of timely DISCOM payables and grid loss reductions accelerates working capital turnover for independent power producers (IPPs).
10. **`sebi_fno_derivative_curbs`** (`capital_markets`):
    - Keywords: `f&o index derivative framework`, `contract size derivatives increased`, `upfront margin derivatives retail`
    - Industries: `Financial Services`
    - Direction: `headwind`, Severity: 7.0
    - Rationale: Stricter derivative entry barriers and higher lot sizes dampen retail options turnover, dampening fee revenues for discount brokers and exchanges.

---

## 5. Non-Causal Regulatory Disclaimer

In compliance with the PRISM Master Authority:
> *"PRISM policy and news signals represent descriptive policy and sector risk pressure, not price prediction or investment advice. Policy announcements may have already been priced into asset valuations by the broader market."*
