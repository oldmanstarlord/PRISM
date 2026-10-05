# PRISM MASTER CONTEXT (applies to every step)

## AUTHORITY
- PRISM_SRS.md is the source of truth. PROJECT_STATUS.md is the living record; follow its Update protocol after every step. docs/archive/ is historical, not requirements. If a prompt conflicts with the SRS, stop and ask.
- Layer 1 (sector-divergence-v1) and Layer 2 (correlation-mst-v1) are approved. Never edit their formulas, windows, thresholds or tie-breaks. A change means a NEW version (v2) added alongside, never an edit.
- PRISM is descriptive risk and explanation, NOT price prediction and NOT investment advice. No look-ahead anywhere. Every score, alert, forecast and scenario must show reason, inputs, thresholds, method version, data age and limitations. MST/correlation is never presented as causal. Shock simulation is a scenario, not a forecast.
- Never print or commit secrets (.env, PRISM_DATABASE_URL). Never invent data, URLs, formulas, regulatory deadlines or results. If something is unspecified, label it ASSUMPTION or TBD and tell me. Respect each data source's terms; prefer official sources; every source sits behind a replaceable adapter (FR-D9).

## DESIGN RULES (this is what "dynamic" means)
- D1 CONFIG-DRIVEN: windows, lookbacks, thresholds, weights, decay half-lives, peer-group rules, event-type mappings and policy rules live in versioned model_config rows (JSON, checksummed, status draft/approved/retired). No magic numbers in code except defaults seeded by migration. Every run stores config_version + config_fingerprint.
- D2 COMPONENT REGISTRY: every risk component is a row in score_component_definition plus a Python class implementing the Component protocol. The scorer, confidence engine, API and frontend read the registry. Adding or reweighting a component must need NO change to scorer, API schema or frontend.
- D3 RESULT ENVELOPE (SRS section 10): every derived result carries subject, effective time, method and version, input fingerprint, lookback, units, component contributions, thresholds, data-sufficiency status, confidence, limitations, computed_at.
- D4 POINT-IN-TIME: external data stores event_time, published_at and ingested_at. After-close publications affect the next trading day (use trading_calendar). Never overwrite; supersede with a new version row. Computing for date t uses only rows with published_at/ingested_at <= t.
- D5 API-DRIVEN UI: the frontend renders breakdowns, limitations, data-age and method info from API payloads using generic shared components. No component or dimension names hard-coded in UI code.
- D6 IDEMPOTENT RUNS: input fingerprint + config fingerprint => identical outputs; a repeat run reuses the completed run and creates no new rows.
- D7 EVERY STEP SHIPS: (1) additive Alembic migration, (2) backend module with typed code and tests, (3) API endpoints with response models, (4) frontend page/components with tests where the step has UI, (5) seed/config entries, (6) docs: PROJECT_STATUS.md update and any proposed SRS decision entries written to docs/specs/PROPOSED_DECISIONS.md (do not edit the SRS yourself).

## AGENT PROTOCOL
1. AUDIT first: read the relevant code, models, migrations and tests. List what already exists and what you will reuse. Do not duplicate or rename existing tables/modules without telling me.
2. PLAN in at most 15 lines (tables, modules, endpoints, pages, tests). Proceed unless you hit an ASK item.
3. IMPLEMENT in this order: migration -> backend -> API -> frontend -> tests -> docs.
4. DATABASE: only additive migrations and the jobs named in the step, and only if the AUTHORIZATION line is present. Before applying, run alembic upgrade <from>:<to> --sql, read it, confirm it is additive, and summarize it for me. Compare row counts of existing tables before and after.
5. GATES (must be run and reported): uv run ruff check . ; uv run mypy ; uv run pytest ; in frontend/: pnpm lint, pnpm test, pnpm build.
6. TESTS must include: hand-calculated numeric cases, determinism (same inputs => same outputs), no-look-ahead, missing-data handling, and idempotent re-run.
7. REPORT (concise): what changed; evidence table (command -> result); decisions you made and any ASSUMPTIONs; anything surprising; what is left. Do not commit or push; leave changes uncommitted.
