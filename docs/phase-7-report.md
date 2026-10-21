# Phase 7 Production Hardening, Release Verification and Viva Pack

Date: 2026-10-20  
Decision: **NO-GO for production**

## Executive conclusion

PRISM's local calculation, UI, and mocked-provider paths are release-candidate quality, but the
system is not production-ready. The user-facing ten-tab application still stores the active
portfolio, research notes, decision journal, review inbox, and comparison snapshots in browser
storage. The authenticated PostgreSQL ledger exists behind separate API/UI code, but it is not
the state authority used by the production ten-tab shell. Consequently, this review cannot prove
multi-device persistence, tenant isolation through the complete UI, or recovery of those records.

The release is also blocked by the absence of a clean-database and restored-copy migration
rehearsal against the intended PostgreSQL/Supabase environment. These are evidence gaps, not
paperwork exceptions, so the decision remains NO-GO.

## Audit scope and evidence

The review covered the FastAPI application, React application, background jobs, SQLAlchemy and
Alembic layers, dependency manifests and lockfiles, CI workflow, operational documentation, all
phase reports, and the actual executable test suites. Historical phase claims were treated as
context and checked against current code rather than accepted as release evidence.

No prices, news, model output, or production performance numbers were invented. Browser release
tests use visibly seeded test records and mocked provider failures. The skipped live-auth browser
case is recorded as a blocker rather than reported as a pass.

## Severity-ranked risk register

| Severity | Finding | Phase 7 disposition |
|---|---|---|
| Critical | None found in the inspected repository | No unresolved critical finding |
| High | The production ten-tab shell uses browser-local portfolio state instead of the authenticated server ledger | **Open; release blocker** |
| High | Notes, journal, review inbox, and user-created comparison snapshots are browser-local and cannot be recovered from PostgreSQL | **Open; release blocker** |
| High | No clean-database or restored-copy migration rehearsal was available in this environment | **Open; release blocker** |
| High | ML and holding-specific news routes were reachable without authentication | Fixed with router-level/current-user dependencies and regression tests |
| High | Anonymous structural-monitoring requests wrote to process-global risk history, enabling cross-request disclosure | Fixed: anonymous history is no longer persisted and the legacy history route returns 410 |
| Medium | API lacked central body limits, request timeout, security headers, and abuse throttling | Fixed with central middleware and bounded schemas; limiter is process-local |
| Medium | News evaluation accepted an arbitrary server-side template path | Fixed: evaluation uses the repository-owned label template only |
| Medium | Curated demo holdings were loaded as the default portfolio | Fixed: empty first run; demo loader is development-only and explicitly labelled DEMO |
| Medium | Risk/stress calculations substituted synthetic price or market series when real observations were unavailable | Fixed: missing real price/benchmark history now returns an explicit validation failure |
| Medium | Generic server failures could expose implementation details through responses/log traces | Fixed: stable generic responses and metadata-only exception logging |
| Medium | Several heavy direct dependencies were unused | Removed from the manifest and lockfile |
| Medium | Rate limiting is per process and therefore not a distributed production quota | **Open; deployment limitation** |
| Medium | Body enforcement depends on `Content-Length`; a streaming proxy limit is still required | **Open; deployment limitation** |
| Low | Live provider reliability, latency, and third-party quota behaviour were not measurable offline | **Open; monitor in staging** |

## Focused changes

### Backend and API

- Added trusted-host validation, request IDs, response hardening headers, a 1 MiB default body
  ceiling, a 60 second request deadline, and bounded process-local throttling for expensive API
  prefixes.
- Added production configuration validation that rejects wildcard/localhost origins and missing
  Supabase authentication configuration.
- Protected all ML routes and holding-specific news routes. Public provider status remains public
  by design and contains no user data.
- Added bounded symbols, collection sizes, text lengths, finite-number validation, and conditional
  ledger transaction validation.
- Limited CSV import bodies and removed the arbitrary evaluation-template path.
- Retired anonymous risk-history retrieval and stopped anonymous structural-monitoring writes.
- Normalized unexpected API failures to non-sensitive responses.

### Frontend and release verification

- API calls now attach the current Supabase bearer token when a session exists.
- Removed automatic curated holdings from first run. Development demo data is explicitly labelled
  and loaded only through a development-only dynamic module.
- Reworded advisory-looking phrases as diagnostics or historical estimates.
- Added Playwright configuration and release regression coverage for the exact ten-tab shell,
  ledger reconciliation, reload persistence, snapshot persistence, and explicit provider-failure
  states. The live authenticated persistence test is intentionally skipped until credentials and a
  disposable test tenant are supplied.

### Dependencies and CI

- Removed unused direct dependencies: `apscheduler`, `arch`, `networkx`, `orjson`, `structlog`,
  `torch-geometric`, and `xgboost`.
- Regenerated `uv.lock` offline from the declared dependency set.
- Kept `torch` and `transformers` because the optional FinBERT implementation imports them; kept
  `yfinance` and `tenacity` because the live market-data path imports them.
- Added Chromium installation and Playwright execution to the frontend CI job.

## Phase 7 file manifest

The focused Phase 7 edits are:

- Runtime/configuration: `.env.example`, `pyproject.toml`, `uv.lock`,
  `.github/workflows/ci.yml`.
- Backend: `backend/app/main.py`, `backend/app/core/config.py`,
  `backend/app/core/security.py`, `backend/app/ml/router.py`, `backend/app/ml/schemas.py`,
  `backend/app/ml/service.py`, `backend/app/ml/registry.py`, `backend/app/news/router.py`,
  `backend/app/news/schemas.py`, `backend/app/portfolio/router.py`,
  `backend/app/portfolio/schemas.py`, `backend/app/portfolio_analytics/router.py`,
  `backend/app/portfolio_analytics/calculator.py`, `backend/app/portfolio_analytics/stock_risk.py`, and
  `backend/app/market_data/live_service.py`.
- Frontend: `frontend/src/api.ts`, `frontend/src/PortfolioManager.tsx`,
  `frontend/src/demoPortfolioData.ts`, `frontend/src/journalAndDecision.test.ts`,
  `frontend/vite.config.ts`, `frontend/playwright.config.ts`, and
  `frontend/e2e/release.spec.ts`.
- Backend tests: `tests/api/test_health.py`, `tests/core/test_config.py`,
  `tests/core/test_security.py`, `tests/market_data/test_live_service.py`,
  `tests/ml/test_ml_api.py`, `tests/news/test_news_intelligence.py`,
  `tests/portfolio_analytics/test_phase3_risk_engine.py`,
  `tests/portfolio_analytics/test_stock_risk.py`, and
  `tests/portfolio_analytics/test_structural_monitoring.py`.
- Documentation: `README.md`, `OPERATIONS.md`, `PROJECT_STATUS.md`,
  `docs/METHODOLOGY.md`, `docs/FEATURE_MATRIX.md`, `docs/VIVA_QA.md`, and this report.

The worktree already contained the prior phase implementation when this audit began; unrelated
dirty files were not reverted or represented as Phase 7 work.

## Quantitative and data-integrity review

The authoritative definitions and formulas remain in `docs/METHODOLOGY.md` and the backend
methodology registry. This phase rechecked the implementation/test relationship for:

- ledger accounting and weighted-average cost-basis reconciliation;
- simple-return portfolio aggregation and buy-and-hold wealth construction;
- annualized covariance volatility and exact Euler component reconciliation;
- discrete-series maximum drawdown;
- historical and Gaussian VaR, historical Expected Shortfall, and exception counts;
- spectral covariance regularization and preservation of negative hedge contributions;
- Mantegna correlation distance and minimum-spanning-tree edge invariants;
- sector divergence benchmarks and insufficient-coverage states;
- walk-forward chronology, reproducibility envelopes, and news/market lineage.

Model outputs, heuristic scores, news sentiment, and stress scenarios remain diagnostic estimates,
not forecasts of certain outcomes or financial advice. Provider failure and insufficient evidence
are represented explicitly; no production fallback synthesizes market prices or headlines.

## Verification record

| Gate | Result on 2026-10-20 |
|---|---|
| Focused security/API regression suite | Passed: 24 tests; 2 warnings |
| Ruff | Passed: 0 errors |
| mypy strict mode | Passed: 0 errors across 84 source files |
| Frontend ESLint | Passed: 0 errors |
| Frontend Vitest | Passed: 56 tests across 10 files |
| Vite production build | Passed |
| Playwright release suite | Passed: 3; skipped: 1 live authenticated persistence case |
| Repository policy/secret-pattern checks | Passed for tracked files and production bundle |
| Full backend pytest | Passed: 142; skipped: 2 guarded DB integration tests; 1 deprecation warning; 15.11s |
| Alembic offline upgrade-to-head compilation | Passed: 750 lines generated through `head` |
| Clean PostgreSQL migration | Not run; no disposable PostgreSQL target supplied |
| Restored-copy migration/rollback rehearsal | Not run; no approved restored target supplied |

The Playwright pass proves browser-local state survival after reload; it does **not** prove
PostgreSQL persistence or tenant isolation. The skipped case prevents a green production verdict.

## Performance and operability

No production workload trace was available, so this phase does not present local timings as
service-level claims or add speculative indexes/caches. Deterministic in-memory profiling on this
review machine produced the following engineering baselines:

| Profile | Input | Wall time |
|---|---|---:|
| Portfolio risk calculation | 200 securities, 252 return observations | 0.043859s |
| Correlation MST | 200 securities, 120 return observations | 1.407251s |
| Volatility walk-forward request path | 300 observations; selected baseline HAR | 1.290910s |
| Ledger replay | 10,001 transactions | 0.034861s |

These are single-run synthetic profiles with deterministic random seeds, not production latency
percentiles. The MST is the dominant profiled quantitative calculation, while the model path is
also materially slower than ledger/risk arithmetic. Before release, staging must capture repeated
p50/p95/p99 timings and peak memory using production-shaped data; query plans must drive any index
changes.

Operational instructions now cover PostgreSQL backup, restore verification, forward migration,
rollback rehearsal, environment validation, health/readiness checks, and provider degradation.
Middleware logs deliberately contain method/path/status/duration/request ID only, not request
bodies, bearer tokens, portfolio holdings, article text, or database URLs.

## Migration and rollback assessment

The repository has a linear Alembic history through the portfolio, risk-history, ML, news, and
Phase 1 audit migrations. Offline SQL generation checks syntax and revision linkage but cannot
establish that a real clean database, an existing production-shaped database, RLS policies, and
rollback/reapply behaviour all work. Release requires both:

1. upgrade a new disposable PostgreSQL database to `head`, run integration tests, and inspect RLS;
2. restore a sanitized backup, record its revision, back it up again, upgrade it, validate row
   counts/constraints/tenant access, rehearse the documented rollback, and reapply.

## Required evidence to change NO-GO to GO

1. Make the authenticated server ledger and portfolio ID the state authority for the ten-tab UI;
   move notes, journal, review inbox, and snapshots to tenant-protected persistence or explicitly
   remove them from the production durability promise.
2. Run the live Playwright flow: create user/portfolio, add-buy-sell, reload, sign out/in, verify
   exact balances and ownership, and delete the test tenant data.
3. Complete clean and restored-copy PostgreSQL migration rehearsals, including RLS isolation and
   rollback/reapply evidence.
4. Replace the process-local expensive-route limiter with a shared quota at the gateway or Redis,
   and enforce request-size/time limits at the reverse proxy.
5. Run representative staging performance and provider-degradation tests and record the measured
   budgets in `OPERATIONS.md`.

Until all five items have evidence, Phase 7 remains **Partial / NO-GO**.
