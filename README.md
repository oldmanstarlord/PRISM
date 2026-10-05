# PRISM

PRISM is a local-first, explainable portfolio-risk and market-intelligence platform
for the NIFTY 200 universe. It uses end-of-day prices. It is not a price predictor or
investment adviser; correlations are non-causal and shocks are scenarios.

The authoritative requirements are in [PRISM_SRS.md](PRISM_SRS.md). Current implementation state and every material project update are recorded in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Repository layout

```text
backend/app/api/   FastAPI routes
backend/app/core/  Application configuration
backend/app/db/    Database connection and models
backend/app/market_data/  Daily prices, corporate actions and quality checks
backend/app/operations/   Scheduler, freshness, alerts and watchlists
frontend/          React and TypeScript dashboard
jobs/              Runnable ingestion and maintenance jobs
tests/             Tests grouped by the component they cover
data/demo/         Explicitly synthetic demonstration portfolios
```

## Local development

1. Copy `.env.example` to `.env` and change secrets when appropriate.
2. Create a Supabase project and place its session-pooler PostgreSQL URL in `.env` as `PRISM_DATABASE_URL`.
3. Run `uv sync --all-groups`.
4. Apply database migrations with `uv run alembic upgrade head`.
5. Seed foundation records with `uv run python -m jobs.seed_universe`.
6. Import the current NIFTY 200 membership with `uv run python -m jobs.import_nifty200`.
7. Import or incrementally update daily prices with `uv run python -m jobs.ingest_prices`.
   Use `--symbols OIL ONGC` for a targeted retry or update.
8. Calculate and persist the latest Layer 1 results with
   `uv run python -m jobs.calculate_sector_divergence`.
   Optional reproducibility controls are `--signal-date`, `--lookback-start` and
   timezone-aware `--data-cutoff`.
9. Calculate and persist the latest Layer 2 correlation MST with
   `uv run python -m jobs.calculate_mst`.
   Optional reproducibility controls are `--window-end`, `--lookback-start` and
   timezone-aware `--data-cutoff`.
10. Start the API with `uv run uvicorn backend.app.main:app --reload`.
11. In `frontend`, run `pnpm install` and `pnpm dev`. The dashboard reads the API from
    `VITE_API_URL`, defaulting to `http://localhost:8000/api/v1`.

## Operations and demonstration

- One daily DAG: `uv run python -m jobs.run_scheduler --once`
- Long-running scheduler: `uv run python -m jobs.run_scheduler`
- Seven-day soak: `uv run python -m jobs.run_scheduler --soak-days 7`
- Key-table export: `uv run python -m jobs.export_key_tables`
- Demo fixtures: `uv run python -m jobs.load_demo_portfolios`
- Demo flow: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Honest limitations: [docs/SRS_FINAL_AUDIT.md](docs/SRS_FINAL_AUDIT.md)

## Verification

Run `uv run ruff check .`, `uv run mypy`, and `uv run pytest`. In `frontend`, run
`pnpm lint`, `pnpm test`, `pnpm build`, and `pnpm test:e2e`.

Backend, frontend and jobs run as native local processes; PostgreSQL is managed by Supabase.

The project is currently in Phase 0. See the status tracker before beginning work.
