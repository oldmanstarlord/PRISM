# PRISM

PRISM is a diagnostic portfolio-risk and market-intelligence application for the NIFTY 200
universe. It measures and explains historical risk, concentration, co-movement, stress scenarios,
news context, and model-estimated risk. It does not issue buy/sell advice or forecast price
direction.

The current release evidence is in [docs/phase-7-report.md](docs/phase-7-report.md), the formulas
and assumptions are in [docs/METHODOLOGY.md](docs/METHODOLOGY.md), and the implementation history
is in [PROJECT_STATUS.md](PROJECT_STATUS.md).

The temporal heterogeneous GNN research and validation pipeline is documented in
[docs/TEMPORAL_HETERO_GNN.md](docs/TEMPORAL_HETERO_GNN.md). Its authenticated API and UI
remain unavailable or visibly research-only until point-in-time, baseline, stability and
relation-ablation gates pass.

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

   From the project root on macOS/Linux, run `./run.sh` to start both the API and
   frontend together. Keep this terminal open; Ctrl+C stops services started by
   the launcher. If a healthy PRISM API is already running on port 8000, the
   launcher reuses it and leaves it running when you stop the frontend.
   Running only the frontend leaves data pages unable to reach the API.

   Alternatively, run each command below in a separate terminal:

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

For local development without Supabase, set `PRISM_LOCAL_AUTH_ENABLED=true`. Requests without a
bearer token then use one fixed local-development identity. This bypass is rejected when
`PRISM_ENVIRONMENT=production` and must not be used for a shared deployment.

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
- News discovery, feeds, portfolio sentiment and decision-engine news scores use a rolling
  seven-day publication window (168 hours). Undated, timezone-free and future stories are
  excluded even if recently fetched. Dates are displayed in IST; midnight does not clear the feed.
- Older material-event stories stay as labelled context when a report in the current window
  matches the company, event category and at least two headline topic words. This transparent
  relevance heuristic is reassessed on every read; a company mention alone is insufficient.
  Context stays outside seven-day sentiment averages and counts. If supporting coverage ages
  out, the story leaves the active feed. A 30-day review archive is kept; still-supported context
  survives archive cleanup even beyond 30 days. Duplicate reprints never inflate sentiment.
- `PRISM_NEWS_AUTO_REFRESH=true` enables collection on API startup, hourly by default, and at
  midnight IST. The API must remain running; refresh cooldowns, shared-cache locks and the
  configured daily Firecrawl credit budget still apply. Missing seven-day coverage stays empty.
  Collection runs in a separate, time-bounded process so native NLP failures cannot stop the API.
- `PRISM_SECTOR_AUTO_REFRESH=true` refreshes price inputs and recalculates sector divergence
  every 30 minutes, anchored to the NSE equity open: 09:15, 09:45, ... 15:15 IST.
  The scheduler pauses at 15:30 and resumes at the next trading session. It checks the
  session clock once a minute, including on startup; dashboard polling reads the published
  result rather than recalculating it. The API must remain running.
- Exchange `trading_calendar` rows override the bundled official 2026 holiday calendar and
  define special-session times. Other years require verified calendar rows. The regular
  schedule follows [NSE equity timings](https://www.nseindia.com/static/market-data/market-timings)
  and [2026 holiday circular](https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf).
  Provisional current-session daily bars update the 1/5/20-day calculations; they are labelled
  separately from final closing prices. These remain trading-day horizons, not 30-minute bars.
  PostgreSQL advisory locking and completed-slot records prevent duplicate worker publications.
  Missing current-session coverage or failed calculations preserve the previous published result
  and expose a refresh error. Transient failures retry after five minutes during the session.
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
backend/app/       API, configuration, database, analytics, news, and ML services
frontend/          React application, unit tests, and Playwright browser tests
jobs/              ingestion, calculations, training, verification, and recovery jobs
migrations/        ordered Alembic revisions
tests/             backend unit, security, quantitative, and opt-in database tests
docs/              methodology, phase reports, release evidence, and viva pack
data/              ignored raw/processed/model artifacts plus labelled evaluation inputs
```

## Backend launcher and pip installs

Start the API with `./backend/run.sh` (or `./run.sh` from `backend/`). The launcher
uses the locked project Python environment even when Conda base is active.
Configuration loads the project-root `.env` regardless of the launch directory.

For a pip-only setup, use Python 3.12 and `python -m pip install -r requirements.txt`
from the root, or `backend/requirements.txt` from the backend directory. Regenerate
the runtime export after dependency changes with:

```sh
uv export --locked --no-dev --no-emit-project --no-hashes --no-annotate --output-file requirements.txt
```

The `vatsal` branch also includes the historical fundamental regression workflows
documented in [FUNDAMENTALS.md](FUNDAMENTALS.md).
