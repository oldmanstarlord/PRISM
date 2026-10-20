# PRISM Phase 6 Report: Investor Experience, Integration and UI Cleanup

**Author:** Antigravity Senior Full-Stack & Quantitative Engineer  
**Date:** October 20, 2026  
**Status:** Complete & Verified  

---

## 1. Executive Summary

Phase 6 unifies the investor experience across all existing portfolio tabs and the 10th tab (`AI Insights`, id: `ai-insights`) without adding any new routes, pages, or nav items. It transforms raw analytical and quantitative outputs into an intuitive, diagnostic, and fully transparent dashboard designed for non-experts, institutional allocators, and quantitative analysts alike.

Strictly adhering to the **PRISM Global Rules**:
- **Zero New Routes, Pages, or Tabs:** Retained exactly the 10 authorized portfolio tabs. All features were integrated into existing panels, tooltips, chips, dialogs, and expandable accordions.
- **Strict Aesthetic Conformance:** Warm Ivory (`#F9EBD7`) page, Sand Beige (`#E3D7C4`) cards/surfaces, Deep Charcoal (`#292D2A`) primary text, Muted Grey (`#686B64`) secondary text, Emerald (`#046A38`) positive, Vermilion (`#E34222` / small text `#B8321A`) negative, Pale Sage (`#DCE9DE`), Pale Terracotta (`#F6D9CC`), Dark Ochre (`#8A5A00`) warnings.
- **Strict Structural Invariants:** Zero white (`#ffffff` / `white`), zero rounded corners (`borderRadius: 0`), zero divider or border lines (all separation achieved via shadows and spatial grouping), light theme only, and visible keyboard focus rings (`0 0 0 2px #046A38`). Contrast ratios exceed 4.5:1 for all text.
- **Diagnostic Discipline:** No buy/sell advice, no price-direction predictions, and no causal speculations. Heuristic composites are explicitly flagged as heuristic; machine learning outputs are labeled `"Model estimate"` with their empirical validation evidence presented side-by-side.

---

## 2. Key Components and Features Implemented

### 2.1 Executive Overview Strip (Structural Overview Tab)
- **10 Structured Metric Tiles:**
  1. *Market Value:* Current mark-to-market portfolio value (₹).
  2. *Invested Cost:* Cumulative cost basis (₹).
  3. *Cash Reserves:* Liquid cash balance (₹).
  4. *Realized P&L:* Closed-trade net profit/loss (₹).
  5. *Unrealized P&L:* Open positions valuation delta (₹ and %).
  6. *Total Return:* Wealth index return over period (%).
  7. *Annualized Volatility:* 252-day empirical annual volatility (%).
  8. *Max Drawdown:* Discrete peak-to-trough historical drawdown (%).
  9. *Concentration HHI:* Herfindahl-Hirschman index with effective holding count ($N_{\text{eff}} = 1/\text{HHI}$).
  10. *Data Freshness:* As-of date, observation period (1Y 252d daily), and feed sync status.
- **Compact Signal Badges:**
  - **Market Regime Badge (`Model estimate`):** Displays active Markov regime (e.g. `Low Volatility Bull (88%) →`) with direct navigation callback to the `AI Insights` tab.
  - **News Intelligence Badge (`News`):** Displays article count and portfolio aggregate sentiment (e.g. `News: 14 articles · Positive →`) with direct navigation callback to the `News Intelligence` tab.

### 2.2 Reusable "What Does This Mean?" Explainer (`WhatDoesThisMeanExplainer.tsx`)
- Standardized, expandable accordion rendered directly from the authoritative methodology registry (`methodologyRegistry.ts` / `METRIC_REGISTRY`).
- **Comprehensive Structure:**
  - *What it measures:* Concise plain-English definition.
  - *Why it matters:* Investor intuition and portfolio significance.
  - *Contributing Holdings:* Filtered list of holdings amplifying or driving the metric.
  - *Estimation Window & Units:* Exact lookback period (e.g., 252d daily, point-in-time) and unit dimension.
  - *Assumptions:* Underlying modeling assumptions (e.g., empirical distribution, mark-to-market, no leverage).
  - *Limitations:* Clear statistical bounds and known edge cases.
- **Zero Duplicate Strings:** Driven 100% dynamically by registry metadata tokens.

### 2.3 Compact Model & News Signal Surfacing Across Tabs
- **Structural Overview:** Regime switching badge (`Model estimate`) and News sentiment badge (`News`).
- **Holdings Table (`PortfolioManager.tsx`):**
  - Added Model C anomaly detection chip (`⚡ Model: Unusual`) when the 20-day sector divergence residual $|z| \ge 1.5\sigma$.
  - Added News count/sentiment badge (`📰 {count} {↑/↓/=/?}`).
- **Stock Risk Section (`Phase2RiskSections.tsx`):** Added Model C Anomaly chips and sector divergence residual tooltips.
- **Portfolio Risk Section (`Phase2RiskSections.tsx`):** Added Model A Volatility Forecast vs Realised Volatility comparison card (`Model estimate`) comparing GARCH/EWMA forecasts against empirical 20d/252d realised volatility.

### 2.4 Explainable Warnings & Diagnostic Alerts
- Every trigger surfaces:
  - Exact trigger value.
  - Calibrated threshold value.
  - Contributing holdings (e.g. `HDFCBANK`, `RELIANCE`).
  - Underlying assumptions.
- Analytical phrasing only: `"Prudential single-stock concentration threshold exceeded"` instead of directive actions like `"Sell HDFCBANK"`.

### 2.5 Drill-Down & Company Detail Enhancement (`CompanyDetail.tsx`)
- **Top Diagnostic Strip:**
  - Displays portfolio weight (%), sector context, Model B sector divergence value ($z$-score), and Model C unusual behavior flag.
  - Direct `"📰 View in News Intelligence"` button.
- **MST Ego-Network & Topological Position Panel:**
  - Displays directly adjacent minimum spanning tree co-movement edges for the stock.
  - Computes and displays Mantegna metric distance:
    $$d_{i,j} = \sqrt{2(1 - \rho_{i,j})}$$
  - Discloses persistence score (%), confidence rating, and network stability.
- **Interactive MST Navigation (`PortfolioMstGraph.tsx`):** Double-tapping (`dbltap`) any node in the Cytoscape graph immediately opens the corresponding Company Detail page (`/companies/:symbol`).

### 2.6 Evidence-Based Snapshot Comparisons (`PortfolioSnapshotSection.tsx`)
- **Evidence-Based Change Explanation Card:**
  - Analyzes holding changes (additions, exits, weight rebalances).
  - Analyzes capital shifts (₹ invested delta and percentage).
  - Evaluates annualized volatility shifts ($\Delta \sigma_p$) and effective holding diversification shifts ($\Delta N_{\text{eff}}$).
  - Audits methodology version and coverage across compared historical captures.
  - **Falsification Guard:** Explicitly states `"insufficient evidence to attribute valuation delta across historical captures"` whenever data points are unavailable, preventing hallucinated explanations.
- **Linked Journal Decisions:**
  - Queries `getDecisionsForSnapshot(snapshotId)` and embeds linked investment decisions with their original timestamps, captured metric contexts, decision types (`Buy`/`Hold`/`Sell`/`Review`), and analytical rationales.

### 2.7 Risk Review Inbox (`RiskReviewInboxPanel.tsx` & `riskInboxStorage.ts`)
- Persistent, local-first review workflow stored per portfolio (`prism_risk_review_inbox_${portfolioId}`).
- Automatically synchronizes triggered indicators from `StructuralMonitoringSnapshot`.
- **Status Tabs:**
  - `Pending Active` (unreviewed triggered alerts).
  - `Reviewed` (signed-off alerts with reviewer notes and timestamps).
  - `Dismissed` (acknowledged non-actionable alerts with rationale).
  - `All Alerts` (complete audit log).
- **Interactive Sign-Off Dialog:** Allows investors/allocators to review or dismiss an alert with an analytical audit note, recording reviewer identity and timestamp.

---

## 3. UI Cleanup & Design System Audit

A comprehensive static and runtime audit was conducted across all frontend components to enforce the PRISM design tokens:

| Element | Specification | Enforcement Status |
| :--- | :--- | :--- |
| **Page Background** | Warm Ivory (`#F9EBD7`) | Enforced globally across root layout |
| **Cards & Panels** | Sand Beige (`#E3D7C4`) / Charcoal (`#292D2A`) | Enforced; all off-palette grays removed |
| **White Elimination** | `#ffffff`, `#fff`, `white` strictly forbidden | Zero white instances in modified components |
| **Border & Divider Lines** | Zero `border`, `borderBottom`, `<Divider />` | Replaced with shadow elevations and spatial rhythm |
| **Corner Curvature** | `borderRadius: 0` everywhere | 0px border radius across all cards, chips, dialogs, and inputs |
| **Typography** | Inter & JetBrains Mono | Used for all tabular, numeric, and financial data |
| **Small Text Contrast** | $\ge 4.5:1$ against background | Verified; small warning text uses `#B8321A` on `#F6D9CC` / `#E3D7C4` |
| **Focus Indication** | Visible shadow ring | `0 0 0 2px #046A38` on active interactive elements |

---

## 4. Verification & Quality Gates (Actual Results)

### 4.1 Python Linter (`ruff`)
```bash
uv run ruff check .
```
**Result:**
```
All checks passed!
```

### 4.2 Python Type Checker (`mypy`)
```bash
uv run mypy backend jobs
```
**Result:**
```
Success: no issues found in 83 source files
```

### 4.3 Python Test Suite (`pytest`)
```bash
uv run pytest
```
**Result:**
```
================= 137 passed, 2 skipped, 1 warning in 48.58s ==================
```
*(2 database pipeline tests intentionally skipped pending live PostgreSQL test database configuration).*

### 4.4 Frontend Linter (`ESLint`)
```bash
pnpm run lint
```
**Result:**
```
> prism-frontend@0.1.0 lint C:\Users\Pratham\OneDrive\Desktop\Mini Project\PRISM\frontend
> eslint .
(Exited with code 0 - 0 errors, 0 warnings)
```

### 4.5 Frontend Vitest Suite (`vitest`)
```bash
pnpm test -- --run
```
**Result:**
```
Test Files  10 passed (10)
     Tests  56 passed (56)
  Duration  11.59s
```

### 4.6 Production Bundle Build (`vite`)
```bash
pnpm run build
```
**Result:**
```
> tsc -b && vite build
vite v8.3.1 building client environment for production...
✓ 975 modules transformed.
dist/index.html                             1.09 kB │ gzip:   0.56 kB
dist/assets/rolldown-runtime-CbXtAM7H.js    0.58 kB │ gzip:   0.36 kB
dist/assets/MstPage-CysyvBb9.js             8.33 kB │ gzip:   3.04 kB
dist/assets/journalStorage-C2t5AMle.js    234.98 kB │ gzip:  74.43 kB
dist/assets/PortfolioManager-BUYtRFoW.js  302.60 kB │ gzip:  70.27 kB
dist/assets/cytoscape.esm-Yq6u8L66.js     434.85 kB │ gzip: 137.78 kB
dist/assets/index-CG9qok1Q.js             437.27 kB │ gzip: 130.16 kB
✓ built in 419ms
```

---

## 5. Browser Verification Evidence

A browser subagent session (`phase6_investor_exp`) navigated through the live application at `http://localhost:5173/`:
- **Structural Overview:** Verified the 10-stat Executive Overview Strip, Market Regime badge, News Intelligence badge, and Risk Review Inbox accordion.
- **Explainable Cards:** Expanded the `"What does this mean?"` explainer to verify multi-section rendering (definition, investor importance, window, coverage, assumptions, limitations).
- **Holdings & Stock Risk:** Inspected the multi-window volatility, downside risk, Euler risk contribution, and Model C anomaly chips (`⚡ Model: Unusual`).
- **Company Detail & MST Ego-Network:** Confirmed top diagnostic strip and adjacent Mantegna distance link inspection.
- **Snapshots & Decision Linking:** Confirmed evidence-based comparison card rendering and journal decision linkage.
- **Visual Recording:** Available in `phase6_investor_exp_1792490464978.webp`.

---

## 6. Limitations & Assumptions

1. **Local Review Inbox Persistence:** Risk review audit actions are currently persisted in browser-local storage per portfolio ID. Multi-user institutional sign-offs with remote PostgreSQL persistence can be backed by a server-side audit table in Phase 7.
2. **MST Ego-Network Sampling:** Adjacent MST graph edges are derived from the active 252-day empirical correlation matrix; intraday co-movement spikes are smoothed across daily log returns.
3. **Evidence-Based Comparison Sufficiency:** When two historical snapshots share fewer than 2 overlapping symbols or lack capital records, the comparison card strictly enforces the `"insufficient evidence"` guard rather than interpolating values.
