# PRISM operations and recovery

## Clean setup

1. Install Python 3.12, `uv`, Node.js 24 and pnpm 10.16.1.
2. Clone the repository and copy `.env.example` to `.env`.
3. Set `PRISM_DATABASE_URL` to the SSL-required Supabase session-pooler URL.
4. Run `uv sync --locked --all-groups`.
5. Run `pnpm install --frozen-lockfile` in `frontend`.
6. Run `uv run alembic upgrade head`.
7. Run `uv run python -m jobs.seed_universe` and
   `uv run python -m jobs.import_nifty200`.
8. Run the first daily workflow with `uv run python -m jobs.run_daily_pipeline`.
9. Start the API and frontend using the commands in `README.md`.

## Daily workflow

Run after the market's validated daily data is available:

```powershell
uv run python -m jobs.run_daily_pipeline
```

The workflow downloads and validates prices, then calculates Layer 1 and Layer 2. New analytical
runs are committed together. A partial ingestion or calculation failure leaves the previous
successful analytical results published and records the failed stage.

For deterministic recovery using the latest already-stored snapshot:

```powershell
uv run python -m jobs.run_daily_pipeline --skip-ingestion
```

## Interrupted-run recovery

An operating-system interruption can leave a `pipeline_run` marked `running`. After confirming no
pipeline process is active, mark records older than two hours failed:

```powershell
uv run python -m jobs.recover_pipeline_runs --older-than-minutes 120
```

This changes only run status; it does not delete prices or replace published Layer 1/2 results.

## Verification

Run the read-only, real-data reproducibility and performance audit:

```powershell
uv run python -m jobs.verify_phase0
```

Run all local checks:

```powershell
uv run ruff check backend jobs tests
uv run mypy backend jobs
uv run pytest -m "not integration"
uv run alembic upgrade head --sql
uv run python -m jobs.check_repository_policy
pnpm.cmd --dir frontend lint
pnpm.cmd --dir frontend test
pnpm.cmd --dir frontend build
```

Database integration tests are deliberately opt-in because they may create a missing deterministic
run. Use only an explicitly approved PostgreSQL test database:

```powershell
$env:PRISM_RUN_DB_INTEGRATION="1"
uv run pytest -m integration
```

## Failure diagnosis

- `/api/v1/ready` checks database connectivity.
- `/api/v1/pipeline/status` reports the latest stage, last success, market/result dates and staleness.
- A `partial` market ingestion must be recovered before analytics are published.
- Never delete the last successful price or analysis revision to recover a failed run.
- Re-run migrations before diagnosing missing-table API failures.
