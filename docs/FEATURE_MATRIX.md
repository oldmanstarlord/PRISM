# PRISM Ten-Tab Feature Matrix

Status distinguishes code existence from independently exercised behaviour. “Verified” means a
test or browser check was run in this Phase 7 workspace; it does not imply live-provider or live
Supabase verification.

| # | Tab (id) | Code present | Independently verified | Release status | Evidence / gap |
|---:|---|---|---|---|---|
| 1 | Structural Overview (`monitoring`) | Yes | Partial | Partial | Component/unit coverage and ten-tab browser shell pass; live portfolio calculations were not browser-verified against Supabase. |
| 2 | Holdings Dashboard (`dashboard`) | Yes | Partial | Partial | Empty state, ledger-derived holding, and reload persistence pass mocked Playwright; primary UI remains browser-local rather than owner-scoped server state. |
| 3 | Stock Risk Analysis (`stock-risk`) | Yes | Partial | Partial | Quantitative backend tests cover multi-window metrics and formulas; no live browser/provider run in Phase 7. |
| 4 | Portfolio Risk & History (`portfolio-risk`) | Yes | Partial | Partial | Risk-engine tests and IndexedDB snapshot persistence pass; browser snapshot/history is not server-side multi-user persistence. |
| 5 | Sector Exposure (`sector-exposure`) | Yes | Partial | Partial | Calculation code and unit tests exist; current-universe survivorship and missing live DB browser rehearsal remain. |
| 6 | Diversification (`diversification`) | Yes | Partial | Partial | HHI, effective counts, diversification ratio, and Euler invariants have mathematical tests; live end-to-end data path is unverified. |
| 7 | Network & Stress (`analysis`) | Yes | Partial | Partial | MST and stress unit tests exist and tab shell passes; real-data browser rendering/performance was not rerun in Phase 7. |
| 8 | News Intelligence (`news-preview`) | Yes | Partial | Partial | Provider-unavailable UI and NLP unit tests pass; live RSS/licensed ingestion and credentials were unavailable. |
| 9 | Transaction Ledger (`transactions`) | Yes | Partial | Partial | Backend authorization/ledger tests and local browser reconciliation/reload pass; the ten-tab UI ledger is not wired to the authenticated server ledger. |
| 10 | AI Insights (`ai-insights`) | Yes | Partial | Partial | ML model/API tests and failure-state browser test pass; ML routes now require auth, but live model artifacts and authenticated browser inference were not exercised. |

No tab is classified Complete for production because the authenticated, persistent, live-provider
journey has not been independently verified end to end. The development-only curated portfolio is
labelled `DEMO` and excluded from production builds by `import.meta.env.DEV`.
