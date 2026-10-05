# SRS Sections 16 and 20 final audit

Date: 2026-10-06. “Complete” means implementation and automated evidence exist; it
does not override the explicit NOT DONE items below.

## Section 16

- [x] Versioned NIFTY 200 source — universe snapshot/membership tables and importer.
- [x] ISIN identity and aliases — `security` and versioned `security_alias`.
- [x] Raw/adjusted prices with ingestion metadata — models, adapter and tests.
- [x] Corporate-action provenance — versioned action rows and raw snapshots.
- [x] Duplicate/gap/OHLC/suspicious-move checks — market-data quality tests.
- [x] Last-known-good preservation — failure-injection tests and isolated manifests.
- [x] Layer 1/2 contracts approved — SRS decisions D20/D21; frozen code has no diff.
- [x] Layer 1/2 documented/tested — component suites and API/UI evidence.
- [x] Reproducible covariance/correlation — input/config fingerprints and tests.
- [x] MST connected/acyclic/`N-1` — calculator/service tests.
- [x] Deterministic reruns — idempotency tests across layers and score runs.
- [x] Walk-forward prohibits shuffle — `validation/splits.py` tests.
- [x] Alembic reproducibility — one head `c5d6e7f8a914`, offline SQL inspected.
- [x] Automated gates — Ruff, mypy, pytest, ESLint, Vitest, build and Playwright.
- [x] Secret/restricted-data guard — ignored `.env`, fixture-path audit.
- [ ] Independent setup/recovery sign-off — NOT DONE; requires another person.

## Section 20 definition of done

- [x] Requirement references are recorded in specs, tests and status entries.
- [x] Automated tests cover implemented paths and error states.
- [x] Inputs/outputs/errors are documented in specs and API schemas.
- [x] Security/data-quality checks are present for the local single-user boundary.
- [x] Acceptance evidence is linked from `PROJECT_STATUS.md` and this audit.
- [x] User views carry explanations and mandatory disclaimers.
- [ ] Clean out-of-sample score conclusion — NOT DONE; validation execution is
  blocked by quarantined fixture-derived database rows.

## Other NOT DONE items

- Seven elapsed days of scheduler soak evidence are not available yet.
- Supabase restore has not been independently executed and signed off.
- Historical NIFTY 200 membership is unavailable; validation has survivorship bias.
- Shares-outstanding coverage is incomplete and the benchmark is single-source.
- Legacy Alembic model/index naming drift remains a separate audited task.
