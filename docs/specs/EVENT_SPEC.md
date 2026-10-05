# PRISM Corporate Announcements & Explainable Events Specification

**Document Version:** 1.0.0  
**Effective Date:** 2026-10-05  
**Step:** 10  
**Status:** Approved Implementation  

---

## 1. Overview & Architectural Principles

PRISM Step 10 introduces the **Corporate Announcements & Explainable Events Engine** and activates the **`event_risk_pressure`** risk component under the `events` dimension (10% target weight in `prism-risk-score-v1`).

### Production source status

The live corporate-announcement source is **TBD**. PRISM does not scrape undocumented
exchange endpoints. Production ingestion requires an explicit export from a verified
official feed or licensed provider; with no export file, the job exits without writing.

### Core Design Rules Enforced
1. **Config-Driven (D1):** Classification mappings (`event_rule`), base importance weights, magnitude multipliers, and recency half-lives reside in versioned database tables and `model_config` entries.
2. **Component Registry (D2):** `EventRiskPressureComponent` implements the `Component` protocol and is registered dynamically with zero changes required to existing scorer logic.
3. **Result Envelope & Transparency (D3):** Scored events return full lineage: base weight, magnitude multiplier, parsed rationale, linking method, classification rule, sentiment probabilities, and evidence spans.
4. **Point-in-Time Integrity (D4):** Effective trading dates are mapped strictly to `trading_calendar`. Announcements published after market close (15:30 IST) or on weekends roll over to the next trading session. Look-ahead leakage is prohibited.
5. **API-Driven UI (D5):** Shared interactive `Timeline` component dynamically renders pricing context, event pins, sentiment badges, importance gauges, and source links.
6. **Descriptive Risk Mandate:** All views and endpoints explicitly display:
   > *"Markets may have already priced this in. PRISM event signals are descriptive risk indicators and not investment advice or directional forecasts."*

---

## 2. Database Schema (`d0e1f2a3b410`)

### `event_rule`
Dynamic mapping rules from source exchange categories into canonical event types.
- `id` (UUID PK)
- `rule_key` (VARCHAR unique)
- `source_category` (VARCHAR)
- `event_type` (VARCHAR)
- `risk_relevant` (BOOLEAN)
- `direction` (VARCHAR: `positive`, `negative`, `neutral`)
- `version` (VARCHAR)
- `active` (BOOLEAN)

### `event_item`
Normalized point-in-time corporate announcement record linked to security.
- `id` (UUID PK)
- `source_document_id` (UUID FK -> `source_document.id`)
- `security_id` (UUID FK -> `security.id`)
- `headline` (VARCHAR 500)
- `body` (TEXT)
- `event_type` (VARCHAR)
- `event_type_method` (VARCHAR: `rule` | `model`)
- `published_at` (TIMESTAMPTZ)
- `effective_trading_date` (DATE)
- `importance` (FLOAT: $[1.0, 10.0]$)
- `importance_components` (JSONB)

### `text_score`
NLP text sentiment and evidence span extraction record.
- `id` (UUID PK)
- `item_id` (UUID FK -> `event_item.id`)
- `model_name` (VARCHAR)
- `model_version` (VARCHAR)
- `sentiment` (VARCHAR: `positive`, `negative`, `neutral`)
- `p_pos` (FLOAT: $[0, 1]$)
- `p_neg` (FLOAT: $[0, 1]$)
- `p_neu` (FLOAT: $[0, 1]$)
- `event_type` (VARCHAR)
- `importance` (FLOAT)
- `evidence_span` (TEXT)
- `scored_at` (TIMESTAMPTZ)

---

## 3. Mathematical Formulations

### 3.1 Event Importance Formula (Resolves OQ-9)
$$\text{importance} = \min\left(10.0, \max\left(1.0, \text{base\_weight} \times \text{magnitude\_multiplier}\right)\right)$$

| Canonical Event Type | Base Weight | Multiplier Triggers | Parsed Multiplier |
| :--- | :--- | :--- | :--- |
| `regulatory_action` | 10.0 | Monetary penalty, SEBI warning, RBI order | $1.5\times$ |
| `debt_rating` | 8.5 | Default in debt servicing, bond coupon delay | $2.0\times$ |
| `debt_rating` | 8.5 | Credit rating downgrade | $1.4\times$ |
| `results` | 8.0 | Quarterly net loss, revenue decline | $1.2\times$ |
| `management_change` | 7.0 | Resignation of Statutory Auditor | $1.5\times$ |
| `management_change` | 7.0 | Resignation of CEO / CFO | $1.3\times$ |
| `promoter_insider` | 6.5 | Invocation of promoter share pledge | $1.4\times$ |
| `ma_order` | 5.0 | Contract win / project order / demerger | $1.0\times$ |
| `dividend` | 3.0 | Dividend declaration / buyback | $1.0\times$ |
| `other` | 2.0 | General compliance announcement | $1.0\times$ |

### 3.2 Recency Decay & Risk Pressure
For a calculation date $t$, each announcement $i$ effective at $t_i \le t$ within a 90-day window has exponential decay:
$$w_i = 2^{-\frac{t - t_i}{\tau}}$$
where $\tau = 14 \text{ days}$ (half-life in config).

Gross negative risk pressure:
$$\text{GrossNeg}(t) = \sum_{i \in \text{Negative}} \text{importance}_i \cdot 2^{-\frac{t - t_i}{14}}$$

Gross positive mitigation:
$$\text{PosMit}(t) = \sum_{j \in \text{Positive}} \text{importance}_j \cdot 2^{-\frac{t - t_j}{14}}$$

Positive offset cap rule: Positive announcements can offset at most 30% of gross negative pressure:
$$\text{AllowedOffset}(t) = \min\left(\text{PosMit}(t), 0.30 \times \text{GrossNeg}(t)\right)$$

$$\text{event\_risk\_pressure}(t) = \max\left(0, \text{GrossNeg}(t) - \text{AllowedOffset}(t)\right)$$

---

## 4. NLP & FinBERT Architecture
- **Model Revision:** Pinned HuggingFace revision `ProsusAI/finbert` (`90eb618b0f7ca7067d2feae4d588523ee734c5db`).
- **Configuration Switch:** `model_config.parameters.finbert_enabled: false` (default off until user approval).
- **Fallback Engine:** Zero-dependency, deterministic financial dictionary scorer with exact keyword polarity matches and evidence extraction.
- **Evaluation Tooling:** `backend/app/events/eval_finbert.py` accepts an explicit labelled CSV. The repository's illustrative examples live under `tests/fixtures/` and are not evaluation evidence.
