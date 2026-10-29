# PRISM
PRISM is an explainable portfolio-risk and market-intelligence platform for the NIFTY 200 universe.

The authoritative requirements are in [PRISM_SRS.md](PRISM_SRS.md). Current implementation state and every material project update are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md).

PRISM is a diagnostic portfolio-risk and market-intelligence application for the NIFTY 200
universe. It measures and explains historical risk, concentration, co-movement, stress scenarios,
news context, and model-estimated risk. It does not issue buy/sell advice or forecast price
direction.

The current release evidence is in [docs/phase-7-report.md](docs/phase-7-report.md), the formulas
and assumptions are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md), and the implementation history
is in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Stack and supported runtimes

- Python 3.12, managed from `pyproject.toml` and `uv.lock` with `uv`.
- Node.js 24 and pnpm 10.16.1, managed from `frontend/package.json` and `pnpm-lock.yaml`.
- FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/Supabase, React 19, TypeScript, MUI v6,
  Cytoscape, Vite, Vitest, and Playwright.

## Reproducible local setup

1. Install Python 3.12, `uv`, Node.js 24, and pnpm 10.16.1.
2. Clone the repository. Do not copy another developer's `.env`.
3. Copy `.env.example` to `.env` and provide the PostgreSQL/Supabase values.
4. Copy `frontend/.env.example` to `frontend/.env`. Only the Supabase URL and publishable key may
   be placed in `VITE_*` variables; never expose database passwords or service-role keys.
5. Install exactly the locked Python environment:

   ```powershell
   uv sync --locked --all-groups
   ```

6. Install exactly the locked frontend environment:

   ```powershell
   pnpm --dir frontend install --frozen-lockfile
   ```

7. Apply migrations and seed/import the market-data foundation:

   ```powershell
   uv run alembic upgrade head
   uv run python -m jobs.seed_universe
   uv run python -m jobs.import_nifty200
   uv run python -m jobs.run_daily_pipeline
   ```

8. Start the services:

   ```powershell
   uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   pnpm --dir frontend dev
   ```

The API defaults to `http://127.0.0.1:8000`; the frontend defaults to
`http://localhost:5173`. Configure `VITE_API_URL` when those differ.

## Configuration and security

Production startup validation rejects wildcard CORS/trusted-host configuration, local CORS
origins, and missing Supabase authentication settings. The API enforces security headers, a 1 MiB
default request limit, a 60-second default timeout, and process-local rate limiting on expensive
analytics/news/ML paths. ML and holding-specific news routes require a valid Supabase bearer token.
Portfolio, transaction, reconciliation, audit, and risk-history queries are owner-scoped.

Override limits only through documented `PRISM_*` environment variables in `.env.example`.
Process-local rate limiting is not a substitute for a shared gateway limiter in a multi-worker
deployment.

## Data and model truth

- Production UI state starts empty. The curated portfolio fixture is available only in Vite
  development mode and is visibly labelled `DEMO`.
- Missing/stale prices, unavailable providers, missing news credentials, and untrained models are
  exposed as unavailable states; they are not replaced with plausible values.
- News is a qualitative diagnostic overlay and never changes covariance, volatility, beta, VaR,
  or Expected Shortfall.
- News feeds show only verified publication timestamps from the current calendar day in
  `Asia/Kolkata` (IST), including portfolio news. Undated, future and previous-day stories are
  hidden even if recently fetched. The browser also expires cards at midnight IST.
- `PRISM_NEWS_AUTO_REFRESH=true` enables collection on API startup, hourly by default, and at
  midnight IST. The API must remain running; refresh cooldowns, shared-cache locks and the
  configured daily Firecrawl credit budget still apply. Missing current-day coverage stays empty.
  Collection runs in a separate, time-bounded process so native NLP failures cannot stop the API.
- ML outputs are labelled model estimates and retain the baseline-fallback governance rule.

## Verification

Run the same release gates used by CI:

```powershell
uv run ruff check .
uv run mypy backend jobs
uv run pytest
uv run alembic upgrade head --sql
uv run python -m jobs.check_repository_policy
pnpm --dir frontend lint
pnpm --dir frontend test -- --run
pnpm --dir frontend build
pnpm --dir frontend test:e2e
```

The Playwright suite includes browser persistence, tab-shell, reconciliation, snapshot, and
provider-outage checks. The live Supabase re-login and cross-session database journey requires a
dedicated test project and credentials and remains a release blocker when those are unavailable.

## Operations and recovery

Use `uv run python -m jobs.run_daily_pipeline` for normal daily operation. Backup, restore,
migration rollback, stale-data handling, and interruption recovery are documented in
[OPERATIONS.md](OPERATIONS.md). Do not run integration tests or migration rehearsals against a
production database.

## Repository layout

```text
backend/app/api/   FastAPI routes
backend/app/core/  Application configuration
backend/app/db/    Database connection and models
backend/app/market_data/  Daily prices, corporate actions and quality checks
frontend/          React and TypeScript dashboard
jobs/              Runnable ingestion and maintenance jobs
tests/             Tests grouped by the component they cover
data/              Ignored local raw, processed and model artifacts
```

## Local development

1. Copy `.env.example` to `.env` and change secrets when appropriate.
2. Create a Supabase project and place its session-pooler PostgreSQL URL in `.env` as `PRISM_DATABASE_URL`.
3. Add the Supabase project URL and publishable key as `PRISM_SUPABASE_URL` and
   `PRISM_SUPABASE_PUBLISHABLE_KEY`. Copy `frontend/.env.example` to `frontend/.env`
   and set the matching public Vite values. Never expose a secret or service-role key.
4. Run `uv sync --locked --all-groups`.
5. Apply database migrations with `uv run alembic upgrade head`.
6. Seed foundation records with `uv run python -m jobs.seed_universe`.
7. Import the current NIFTY 200 membership with `uv run python -m jobs.import_nifty200`.
8. Import or incrementally update daily prices with `uv run python -m jobs.ingest_prices`.
   Use `--symbols OIL ONGC` for a targeted retry or update.
9. Calculate and persist the latest Layer 1 results with
   `uv run python -m jobs.calculate_sector_divergence`.
   Optional reproducibility controls are `--signal-date`, `--lookback-start` and
   timezone-aware `--data-cutoff`.
10. Calculate and persist the latest Layer 2 correlation MST with
   `uv run python -m jobs.calculate_mst`.
   Optional reproducibility controls are `--window-end`, `--lookback-start` and
   timezone-aware `--data-cutoff`.
11. Start the API with `uv run uvicorn backend.app.main:app --reload`.
12. In `frontend`, run `pnpm install --frozen-lockfile` and `pnpm dev`. The dashboard reads the API from
    `VITE_API_URL`, defaulting to `http://localhost:8000/api/v1`.

For routine operation, use `uv run python -m jobs.run_daily_pipeline` instead of invoking each
stage separately. Setup, failure recovery and verification are documented in
[OPERATIONS.md](OPERATIONS.md).

Backend, frontend and jobs run as native local processes; PostgreSQL is managed by Supabase.

Phases 0 and 1 are complete. The current product supports authenticated portfolio snapshots,
session-only portfolio analytics, MST stability confidence, stress scenarios and owner-scoped
audit history. See the status tracker and [portfolio contract](PHASE1_PORTFOLIO_CONTRACT.md).
